import os
from .base import LLMProvider, LLMConfig

def get_llm_provider(call_id: str) -> LLMProvider:
    provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider_name == "openai":
        from .openai import OpenAILLMProvider
        config = LLMConfig(
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "150")),
        )
        return OpenAILLMProvider(call_id=call_id, config=config)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider_name}")
