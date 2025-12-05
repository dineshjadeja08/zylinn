"""
Large Language Model (LLM) Adapter
Provides OpenAI integration with streaming support and retry logic.
"""
import asyncio
import os
from typing import Optional, AsyncIterator
from dataclasses import dataclass
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = structlog.get_logger(__name__)


@dataclass
class LLMConfig:
    """Configuration for LLM"""
    api_key: str
    model: str = "gpt-4-turbo-preview"
    temperature: float = 0.7
    max_tokens: int = 150


class LLMAdapter:
    """
    OpenAI LLM adapter with streaming support.
    
    Handles:
    - Text generation with retry logic
    - Streaming responses
    - Error handling and rate limiting
    """
    
    def __init__(self, call_id: str, config: LLMConfig):
        self.call_id = call_id
        self.config = config
        self.logger = logger.bind(call_id=call_id)
        self._setup_client()
    
    def _setup_client(self):
        """Initialize OpenAI client"""
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=self.config.api_key)
            self.logger.info("openai_client_initialized", model=self.config.model)
        except ImportError:
            self.logger.error("openai_not_installed")
            raise RuntimeError("openai package not installed")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate response from LLM (non-streaming).
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            Generated text response
        """
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            self.logger.info(
                "llm_request",
                prompt_length=len(prompt),
                model=self.config.model
            )
            
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens
            )
            
            generated_text = response.choices[0].message.content
            
            self.logger.info(
                "llm_response",
                response_length=len(generated_text),
                finish_reason=response.choices[0].finish_reason,
                usage=response.usage.total_tokens if response.usage else 0
            )
            
            return generated_text
            
        except Exception as e:
            self.logger.error("llm_generation_failed", error=str(e))
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    async def generate_with_tools(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> dict:
        """
        Generate response from LLM with tool calling support.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            tools: List of tool definitions
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            Dictionary with 'text' (response text) and optional 'tool_calls' (list of tool invocations)
        """
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            self.logger.info(
                "llm_tool_request",
                prompt_length=len(prompt),
                model=self.config.model,
                tools_provided=len(tools) if tools else 0
            )
            
            kwargs = {
                "model": self.config.model,
                "messages": messages,
                "temperature": temperature or self.config.temperature,
                "max_tokens": max_tokens or self.config.max_tokens
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(**kwargs)
            
            message = response.choices[0].message
            result = {
                "text": message.content or "",
                "tool_calls": []
            }
            
            # Extract tool calls if present
            if hasattr(message, 'tool_calls') and message.tool_calls:
                import json
                for tool_call in message.tool_calls:
                    result["tool_calls"].append({
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)
                    })
                    self.logger.info(
                        "llm_tool_call",
                        tool_name=tool_call.function.name,
                        arguments=tool_call.function.arguments
                    )
            
            self.logger.info(
                "llm_tool_response",
                response_length=len(result["text"]),
                tool_calls_count=len(result["tool_calls"]),
                finish_reason=response.choices[0].finish_reason,
                usage=response.usage.total_tokens if response.usage else 0
            )
            
            return result
            
        except Exception as e:
            self.logger.error("llm_tool_generation_failed", error=str(e))
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True
    )
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Generate streaming response from LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Yields:
            Text chunks as they are generated
        """
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            self.logger.info(
                "llm_stream_request",
                prompt_length=len(prompt),
                model=self.config.model
            )
            
            stream = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=temperature or self.config.temperature,
                max_tokens=max_tokens or self.config.max_tokens,
                stream=True
            )
            
            full_response = []
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response.append(content)
                    yield content
            
            self.logger.info(
                "llm_stream_complete",
                response_length=len("".join(full_response))
            )
            
        except Exception as e:
            self.logger.error("llm_stream_failed", error=str(e))
            raise


class MockLLMAdapter:
    """
    Mock LLM adapter for testing.
    
    Returns predefined responses without calling actual LLM API.
    """
    
    def __init__(self, call_id: str, mock_responses: Optional[dict] = None):
        self.call_id = call_id
        self.mock_responses = mock_responses or {}
        self.default_response = "You said: {transcript}"
        self.logger = logger.bind(call_id=call_id, mode="mock")
        self.request_count = 0
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate mock response"""
        self.request_count += 1
        
        # Simulate API delay
        await asyncio.sleep(0.1)
        
        # Check for custom response based on prompt keywords
        for keyword, response in self.mock_responses.items():
            if keyword.lower() in prompt.lower():
                self.logger.info(
                    "mock_llm_response",
                    matched_keyword=keyword,
                    request_count=self.request_count
                )
                return response
        
        # Default response
        response = self.default_response.format(
            transcript=prompt[:100] + "..." if len(prompt) > 100 else prompt
        )
        
        self.logger.info(
            "mock_llm_default_response",
            prompt_length=len(prompt),
            request_count=self.request_count
        )
        
        return response
    
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """Generate mock streaming response"""
        response = await self.generate(prompt, system_prompt, temperature, max_tokens)
        
        # Simulate streaming by yielding word by word
        words = response.split()
        for word in words:
            await asyncio.sleep(0.05)  # Simulate streaming delay
            yield word + " "
        
        self.logger.info("mock_llm_stream_complete")
    
    async def generate_with_tools(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> dict:
        """Generate mock response with tool calls (for testing)"""
        # For mock mode, return empty tool calls
        response = await self.generate(prompt, system_prompt, temperature, max_tokens)
        return {
            "text": response,
            "tool_calls": []
        }


def create_llm_adapter(
    call_id: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    use_mock: bool = False,
    mock_responses: Optional[dict] = None
) -> LLMAdapter | MockLLMAdapter:
    """
    Factory function to create LLM adapter.
    
    Args:
        call_id: Unique call identifier
        api_key: OpenAI API key
        model: Model name (default: gpt-4-turbo-preview)
        use_mock: If True, returns MockLLMAdapter for testing
        mock_responses: Custom responses for mock adapter
        
    Returns:
        LLM adapter instance
    """
    if use_mock:
        return MockLLMAdapter(call_id, mock_responses)
    
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        logger.warning(
            "openai_key_missing",
            call_id=call_id,
            message="Using mock LLM adapter"
        )
        return MockLLMAdapter(call_id, mock_responses)
    
    config = LLMConfig(
        api_key=api_key,
        model=model or os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
        temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "150"))
    )
    
    return LLMAdapter(call_id, config)


# Tool definitions for structured output
BOOKING_TOOL = {
    "type": "function",
    "function": {
        "name": "book_appointment",
        "description": "Book an appointment for the customer after confirming all required details",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "The customer's full name"
                },
                "customer_phone": {
                    "type": "string",
                    "description": "The customer's phone number (optional)"
                },
                "customer_email": {
                    "type": "string",
                    "description": "The customer's email address (optional)"
                },
                "appointment_date": {
                    "type": "string",
                    "description": "The appointment date in format YYYY-MM-DD (e.g., 2024-03-15)"
                },
                "appointment_time": {
                    "type": "string",
                    "description": "The appointment time (e.g., '2:30 PM', '14:30')"
                },
                "service_type": {
                    "type": "string",
                    "description": "Type of service or appointment reason (optional)"
                },
                "notes": {
                    "type": "string",
                    "description": "Any additional notes or special requests (optional)"
                }
            },
            "required": ["customer_name", "appointment_date", "appointment_time"]
        }
    }
}

# Predefined system prompts
SYSTEM_PROMPTS = {
    "default": """You are Zylin, a helpful AI voice assistant. 
You provide concise, clear responses suitable for voice conversations.
Keep your responses brief (1-2 sentences) unless more detail is explicitly requested.""",
    
    "customer_service": """You are Zylin, a professional customer service AI assistant.
You are polite, empathetic, and solution-oriented.
Keep responses concise and actionable.""",
    
    "appointment": """You are Zylin, an AI appointment scheduling assistant for a medical clinic.

Your job is to:
1. Greet callers warmly and ask how you can help
2. Collect required information: customer name, preferred date, and time
3. Optionally collect: phone number, email, service type, and any special notes
4. Confirm all details clearly before booking
5. Use the book_appointment tool ONLY when you have confirmed all required details
6. After booking, provide a clear confirmation with the appointment details

Guidelines:
- Keep responses natural and conversational
- Ask one question at a time
- Clarify any ambiguous information
- Be patient and friendly
- Always repeat back the confirmed details before booking
- If the customer wants to change something, update accordingly before booking

Available time slots: Monday-Friday, 9 AM - 5 PM
Service types: General Consultation, Follow-up, Checkup, Specialist Visit"""
}


def get_system_prompt(prompt_type: str = "default") -> str:
    """
    Get predefined system prompt by type.
    
    Args:
        prompt_type: Type of system prompt ('default', 'customer_service', 'appointment')
        
    Returns:
        System prompt text
    """
    return SYSTEM_PROMPTS.get(prompt_type, SYSTEM_PROMPTS["default"])
