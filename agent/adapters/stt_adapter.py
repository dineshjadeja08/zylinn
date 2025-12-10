"""
Speech-to-Text (STT) Adapter
Provides streaming STT with multiple provider support and mock implementation.
"""
import asyncio
import os
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
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


class STTAdapter(ABC):
    """Abstract base class for STT adapters"""
    
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.logger = logger.bind(call_id=call_id)
    
    @abstractmethod
    async def send_audio_chunk(self, audio_data: bytes):
        """Send audio chunk for transcription"""
        pass
    
    @abstractmethod
    async def get_transcript_stream(self) -> AsyncIterator[TranscriptResult]:
        """Get stream of transcript results (partial + final)"""
        pass
    
    @abstractmethod
    async def reset(self):
        """Reset the transcription session"""
        pass
    
    @abstractmethod
    async def close(self):
        """Close the STT connection"""
        pass


class AssemblyAISTTAdapter(STTAdapter):
    """
    AssemblyAI streaming STT adapter.
    
    Uses AssemblyAI's real-time transcription API.
    """
    
    def __init__(self, call_id: str, api_key: str):
        super().__init__(call_id)
        self.api_key = api_key
        self.client = None
        self.transcriber = None
        self.transcript_queue: asyncio.Queue = asyncio.Queue()
        self._setup_client()
    
    def _setup_client(self):
        """Initialize AssemblyAI client"""
        try:
            import assemblyai as aai
            
            aai.settings.api_key = self.api_key
            
            # Configure real-time transcriber
            self.transcriber = aai.RealtimeTranscriber(
                sample_rate=16_000,
                on_data=self._on_data,
                on_error=self._on_error,
                on_open=self._on_open,
                on_close=self._on_close,
            )
            
            self.logger.info("assemblyai_stt_initialized")
            
        except ImportError:
            self.logger.error("assemblyai_not_installed")
            raise RuntimeError("assemblyai package not installed")
    
    def _on_open(self, session_opened: any):
        """Callback when connection opens"""
        self.logger.info("assemblyai_session_opened")
    
    def _on_data(self, transcript: any):
        """Callback when transcript data received"""
        try:
            result = TranscriptResult(
                text=transcript.text,
                is_final=transcript.message_type == "FinalTranscript",
                confidence=getattr(transcript, 'confidence', 0.0),
                timestamp=asyncio.get_event_loop().time(),
                type=TranscriptType.FINAL if transcript.message_type == "FinalTranscript" else TranscriptType.PARTIAL
            )
            
            asyncio.create_task(self.transcript_queue.put(result))
            
        except Exception as e:
            self.logger.error("transcript_processing_error", error=str(e))
    
    def _on_error(self, error: any):
        """Callback on error"""
        self.logger.error("assemblyai_error", error=str(error))
    
    def _on_close(self):
        """Callback when connection closes"""
        self.logger.info("assemblyai_session_closed")
    
    async def send_audio_chunk(self, audio_data: bytes):
        """Send audio chunk to AssemblyAI"""
        try:
            if not self.transcriber:
                raise RuntimeError("Transcriber not initialized")
            
            # Connect if not connected
            if not hasattr(self.transcriber, '_session_id'):
                self.transcriber.connect()
            
            self.transcriber.stream(audio_data)
            
        except Exception as e:
            self.logger.error("audio_send_failed", error=str(e))
            raise
    
    async def get_transcript_stream(self) -> AsyncIterator[TranscriptResult]:
        """Stream transcript results"""
        while True:
            try:
                result = await asyncio.wait_for(
                    self.transcript_queue.get(),
                    timeout=30.0  # 30 second timeout for keepalive
                )
                yield result
                
            except asyncio.TimeoutError:
                # No transcripts for 30 seconds, send keepalive and continue
                self.logger.debug("assemblyai_stt_keepalive", timeout_seconds=30)
                continue
            except Exception as e:
                self.logger.error("transcript_stream_error", error=str(e))
                # Don't break - continue listening unless explicitly closed
                await asyncio.sleep(1.0)
                continue
    
    async def reset(self):
        """Reset transcription session"""
        if self.transcriber:
            self.transcriber.close()
            await asyncio.sleep(0.1)
            self.transcriber.connect()
        
        # Clear queue
        while not self.transcript_queue.empty():
            self.transcript_queue.get_nowait()
        
        self.logger.info("stt_session_reset")
    
    async def close(self):
        """Close AssemblyAI connection"""
        if self.transcriber:
            self.transcriber.close()
        self.logger.info("stt_closed")


class WhisperSTTAdapter(STTAdapter):
    """
    OpenAI Whisper STT adapter (local or API-based).
    
    Note: Whisper is not truly streaming, so this buffers audio
    and transcribes in chunks.
    """
    
    def __init__(self, call_id: str, use_api: bool = True, api_key: Optional[str] = None):
        super().__init__(call_id)
        self.use_api = use_api
        self.api_key = api_key
        self.audio_buffer = bytearray()
        self.buffer_duration_ms = 2000  # Transcribe every 2 seconds
        self.sample_rate = 16000
        self.bytes_per_ms = (self.sample_rate * 2) // 1000  # 16-bit = 2 bytes per sample
        self.transcript_queue: asyncio.Queue = asyncio.Queue()
        
        if use_api and not api_key:
            raise ValueError("API key required for Whisper API mode")
        
        if not use_api:
            self._load_local_model()
    
    def _load_local_model(self):
        """Load local Whisper model"""
        try:
            import whisper
            self.model = whisper.load_model("base")
            self.logger.info("whisper_local_model_loaded")
        except ImportError:
            self.logger.error("whisper_not_installed")
            raise RuntimeError("whisper package not installed")
    
    async def send_audio_chunk(self, audio_data: bytes):
        """Buffer audio and transcribe when threshold reached"""
        self.audio_buffer.extend(audio_data)
        
        # Check if buffer is full enough to transcribe
        buffer_threshold = self.buffer_duration_ms * self.bytes_per_ms
        
        if len(self.audio_buffer) >= buffer_threshold:
            await self._transcribe_buffer()
    
    async def _transcribe_buffer(self):
        """Transcribe buffered audio"""
        if not self.audio_buffer:
            return
        
        try:
            audio_bytes = bytes(self.audio_buffer)
            self.audio_buffer.clear()
            
            if self.use_api:
                text = await self._transcribe_api(audio_bytes)
            else:
                text = await self._transcribe_local(audio_bytes)
            
            if text:
                result = TranscriptResult(
                    text=text,
                    is_final=True,
                    confidence=0.9,
                    timestamp=asyncio.get_event_loop().time(),
                    type=TranscriptType.FINAL
                )
                await self.transcript_queue.put(result)
                
        except Exception as e:
            self.logger.error("transcription_failed", error=str(e))
    
    async def _transcribe_api(self, audio_bytes: bytes) -> str:
        """Transcribe using OpenAI Whisper API"""
        import openai
        import tempfile
        import wave
        
        # Save to temp WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            with wave.open(f.name, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_bytes)
            
            temp_path = f.name
        
        try:
            client = openai.OpenAI(api_key=self.api_key)
            
            with open(temp_path, 'rb') as audio_file:
                transcript = await asyncio.to_thread(
                    client.audio.transcriptions.create,
                    model="whisper-1",
                    file=audio_file
                )
            
            return transcript.text
            
        finally:
            os.unlink(temp_path)
    
    async def _transcribe_local(self, audio_bytes: bytes) -> str:
        """Transcribe using local Whisper model"""
        import numpy as np
        
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Transcribe
        result = await asyncio.to_thread(
            self.model.transcribe,
            audio_array,
            fp16=False
        )
        
        return result["text"]
    
    async def get_transcript_stream(self) -> AsyncIterator[TranscriptResult]:
        """Stream transcript results"""
        while True:
            try:
                result = await asyncio.wait_for(
                    self.transcript_queue.get(),
                    timeout=300.0  # 5 minutes timeout for persistent agent
                )
                yield result
            except asyncio.TimeoutError:
                # No transcripts for 5 minutes, send keepalive and continue
                self.logger.debug("whisper_stt_keepalive", timeout_seconds=300)
                continue
            except Exception as e:
                self.logger.error("transcript_stream_error", error=str(e))
                # Don't break - continue listening unless explicitly closed
                await asyncio.sleep(1.0)
                continue
    
    async def reset(self):
        """Reset transcription session"""
        self.audio_buffer.clear()
        while not self.transcript_queue.empty():
            self.transcript_queue.get_nowait()
        self.logger.info("stt_session_reset")
    
    async def close(self):
        """Close Whisper adapter"""
        await self._transcribe_buffer()  # Transcribe any remaining audio
        self.logger.info("stt_closed")


class MockSTTAdapter(STTAdapter):
    """
    Mock STT adapter for testing.
    
    Returns predefined transcripts or transcribes from test data.
    """
    
    def __init__(self, call_id: str, mock_transcripts: Optional[list] = None):
        super().__init__(call_id)
        self.mock_transcripts = mock_transcripts or []
        self.transcript_index = 0
        self.audio_buffer_size = 0
        self.transcript_queue: asyncio.Queue = asyncio.Queue()
        self.logger = self.logger.bind(mode="mock")
    
    async def send_audio_chunk(self, audio_data: bytes):
        """Simulate audio processing"""
        self.audio_buffer_size += len(audio_data)
        
        # Simulate transcription every ~32KB (2 seconds at 16kHz)
        if self.audio_buffer_size >= 32000:
            await self._generate_mock_transcript()
            self.audio_buffer_size = 0
    
    async def _generate_mock_transcript(self):
        """Generate mock transcript from predefined list"""
        if self.transcript_index < len(self.mock_transcripts):
            transcript_text = self.mock_transcripts[self.transcript_index]
            self.transcript_index += 1
            
            # Generate partial
            partial_result = TranscriptResult(
                text=transcript_text[:len(transcript_text)//2] + "...",
                is_final=False,
                confidence=0.7,
                timestamp=asyncio.get_event_loop().time(),
                type=TranscriptType.PARTIAL
            )
            await self.transcript_queue.put(partial_result)
            
            # Wait a bit
            await asyncio.sleep(0.1)
            
            # Generate final
            final_result = TranscriptResult(
                text=transcript_text,
                is_final=True,
                confidence=0.95,
                timestamp=asyncio.get_event_loop().time(),
                type=TranscriptType.FINAL
            )
            await self.transcript_queue.put(final_result)
            
            self.logger.info(
                "mock_transcript_generated",
                text=transcript_text,
                index=self.transcript_index
            )
    
    async def get_transcript_stream(self) -> AsyncIterator[TranscriptResult]:
        """Stream mock transcripts"""
        while True:
            try:
                result = await asyncio.wait_for(
                    self.transcript_queue.get(),
                    timeout=30.0  # 30 second timeout for keepalive
                )
                yield result
            except asyncio.TimeoutError:
                # No transcripts for 30 seconds, continue waiting (keepalive)
                self.logger.debug("mock_stt_keepalive", timeout_seconds=30)
                continue
            except Exception as e:
                self.logger.error("mock_stream_error", error=str(e))
                # Don't break - continue listening unless explicitly closed
                await asyncio.sleep(1.0)
                continue
    
    async def reset(self):
        """Reset mock adapter"""
        self.audio_buffer_size = 0
        while not self.transcript_queue.empty():
            self.transcript_queue.get_nowait()
        self.logger.info("mock_stt_reset")
    
    async def close(self):
        """Close mock adapter"""
        self.logger.info("mock_stt_closed")


def create_stt_adapter(
    call_id: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    mock_transcripts: Optional[list] = None
) -> STTAdapter:
    """
    Factory function to create STT adapter.
    
    Args:
        call_id: Unique call identifier
        provider: STT provider ('assemblyai', 'whisper', 'mock')
        api_key: API key for the provider
        mock_transcripts: List of mock transcripts for testing
        
    Returns:
        STT adapter instance
    """
    provider = provider or os.getenv("STT_PROVIDER", "mock")
    api_key = api_key or os.getenv("STT_API_KEY")
    
    logger.info("creating_stt_adapter", call_id=call_id, provider=provider)
    
    if provider == "assemblyai":
        if not api_key:
            logger.warning("assemblyai_key_missing", message="Using mock STT")
            return MockSTTAdapter(call_id, mock_transcripts)
        return AssemblyAISTTAdapter(call_id, api_key)
    
    elif provider == "whisper":
        use_api = api_key is not None
        if use_api:
            return WhisperSTTAdapter(call_id, use_api=True, api_key=api_key)
        else:
            logger.info("using_local_whisper")
            return WhisperSTTAdapter(call_id, use_api=False)
    
    elif provider == "mock":
        return MockSTTAdapter(call_id, mock_transcripts)
    
    else:
        logger.warning("unknown_stt_provider", provider=provider, message="Using mock")
        return MockSTTAdapter(call_id, mock_transcripts)
