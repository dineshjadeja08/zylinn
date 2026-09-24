"""
OpenAI LLM Provider
"""
import asyncio
import os
from typing import Optional, AsyncIterator
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from providers.llm.base import LLMProvider, LLMConfig

logger = structlog.get_logger(__name__)

class OpenAILLMProvider(LLMProvider):
    def __init__(self, call_id: str, config: LLMConfig):
        super().__init__(call_id, config)
        self._setup_client()
        
    def _setup_client(self):
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=self.config.api_key)
        except ImportError:
            raise RuntimeError("openai package not installed")
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type((Exception,)), reraise=True)
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, tools: Optional[list] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> dict:
        if tools is not None:
            return await self.generate_with_tools(prompt=prompt, system_prompt=system_prompt, tools=tools, temperature=temperature, max_tokens=max_tokens)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens
        )
        message = response.choices[0].message
        return {"text": message.content, "tool_calls": []}
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type((Exception,)), reraise=True)
    async def generate_with_tools(self, prompt: str, system_prompt: Optional[str] = None, tools: Optional[list] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
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
        result = {"text": message.content or "", "tool_calls": []}
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            import json
            for tool_call in message.tool_calls:
                result["tool_calls"].append({
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                })
        return result
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type((Exception,)), reraise=True)
    async def generate_stream(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> AsyncIterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        stream = await self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=True
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
