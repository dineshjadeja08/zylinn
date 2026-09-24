"""
Text-to-Speech (TTS) Provider Base
"""
import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator
import structlog

logger = structlog.get_logger(__name__)

class TTSProvider(ABC):
    """Abstract base class for TTS providers"""
    
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.logger = logger.bind(call_id=call_id)
    
    @abstractmethod
    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        """
        Convert text to speech and yield audio chunks.
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close TTS connection"""
        pass
