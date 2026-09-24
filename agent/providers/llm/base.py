"""
Large Language Model (LLM) Provider Base
"""
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class LLMConfig:
    """Configuration for LLM"""
    api_key: str
    model: str = "gpt-4-turbo-preview"
    temperature: float = 0.7
    max_tokens: int = 150

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, call_id: str, config: LLMConfig):
        self.call_id = call_id
        self.config = config
        self.logger = logger.bind(call_id=call_id)
        
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, tools: Optional[list] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> dict:
        pass
        
    @abstractmethod
    async def generate_with_tools(self, prompt: str, system_prompt: Optional[str] = None, tools: Optional[list] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> dict:
        pass
        
    @abstractmethod
    async def generate_stream(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> AsyncIterator[str]:
        pass
