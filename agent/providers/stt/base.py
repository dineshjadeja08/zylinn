"""
Speech-to-Text (STT) Provider Base
"""
import asyncio
from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)

class TranscriptType(Enum):
    """Type of transcript event"""
    PARTIAL = "partial"
    FINAL = "final"

@dataclass
class TranscriptResult:
    """STT transcript result"""
    text: str
    is_final: bool
    confidence: float
    timestamp: float
    type: TranscriptType
    detected_languages: list[str] = None

class STTProvider(ABC):
    """Abstract base class for STT providers"""
    
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.logger = logger.bind(call_id=call_id)
    
    @abstractmethod
    async def send_audio_chunk(self, audio_data: bytes):
        """Send audio chunk for transcription"""
        pass
    
    @abstractmethod
    async def get_transcript_stream(self) -> AsyncIterator[TranscriptResult]:
        """Get stream of transcript results"""
        pass
    
    @abstractmethod
    async def reset(self):
        """Reset the transcription session"""
        pass
    
    @abstractmethod
    async def close(self):
        """Close the STT connection"""
        pass
