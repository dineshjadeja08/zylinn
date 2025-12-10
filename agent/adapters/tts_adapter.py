"""
Text-to-Speech (TTS) Adapter
Provides streaming TTS with multiple provider support and fallback.
"""
import asyncio
import os
import tempfile
from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator
import structlog

logger = structlog.get_logger(__name__)


class TTSAdapter(ABC):
    """Abstract base class for TTS adapters"""
    
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.logger = logger.bind(call_id=call_id)
    
    @abstractmethod
    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        """
        Convert text to speech and yield audio chunks.
        
        Args:
            text: Text to convert to speech
            
        Yields:
            Audio data chunks (PCM16, 16kHz, mono)
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close TTS connection"""
        pass


class ElevenLabsTTSAdapter(TTSAdapter):
    """
    ElevenLabs streaming TTS adapter.
    
    Provides high-quality, low-latency text-to-speech.
    """
    
    def __init__(self, call_id: str, api_key: str, voice_id: Optional[str] = None):
        super().__init__(call_id)
        self.api_key = api_key
        self.voice_id = voice_id or "21m00Tcm4TlvDq8ikWAM"  # Default voice
        self._setup_client()
    
    def _setup_client(self):
        """Initialize ElevenLabs client"""
        try:
            from elevenlabs import generate, stream, Voice
            self.generate_func = generate
            self.stream_func = stream
            self.Voice = Voice
            self.logger.info("elevenlabs_tts_initialized", voice_id=self.voice_id)
        except ImportError:
            self.logger.error("elevenlabs_not_installed")
            raise RuntimeError("elevenlabs package not installed")
    
    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        """Stream speech from ElevenLabs"""
        try:
            self.logger.info("tts_request", text_length=len(text), provider="elevenlabs")
            
            # Use ElevenLabs Python SDK with proper streaming
            try:
                from elevenlabs.client import ElevenLabs
                from elevenlabs import stream as elevenlabs_stream
                
                client = ElevenLabs(api_key=self.api_key)
                
                # Generate audio with streaming enabled
                # ElevenLabs outputs PCM 16kHz by default when using stream
                audio_generator = client.generate(
                    text=text,
                    voice=self.voice_id,
                    model="eleven_turbo_v2",  # Fastest model for real-time
                    stream=True,
                    output_format="pcm_16000"  # 16kHz PCM for LiveKit
                )
                
                # Stream audio chunks
                chunk_count = 0
                for chunk in audio_generator:
                    if chunk:
                        yield chunk
                        chunk_count += 1
                
                self.logger.info("tts_stream_complete", chunks=chunk_count)
                
            except ImportError:
                # Fallback to older elevenlabs API
                self.logger.warning("using_legacy_elevenlabs_api")
                audio_stream = await asyncio.to_thread(
                    self.generate_func,
                    text=text,
                    voice=self.voice_id,
                    model="eleven_turbo_v2",
                    stream=True,
                    api_key=self.api_key
                )
                
                for chunk in audio_stream:
                    yield chunk
                
                self.logger.info("tts_stream_complete")
            
        except Exception as e:
            self.logger.error("tts_stream_failed", error=str(e), voice_id=self.voice_id)
            # Re-raise to allow fallback handling at higher level
            raise
    
    async def close(self):
        """Close ElevenLabs adapter"""
        self.logger.info("tts_closed")


class AzureTTSAdapter(TTSAdapter):
    """
    Azure Cognitive Services TTS adapter.
    
    Provides Microsoft's neural TTS voices.
    """
    
    def __init__(
        self,
        call_id: str,
        subscription_key: str,
        region: str,
        voice_name: Optional[str] = None
    ):
        super().__init__(call_id)
        self.subscription_key = subscription_key
        self.region = region
        self.voice_name = voice_name or "en-US-JennyNeural"
        self._setup_client()
    
    def _setup_client(self):
        """Initialize Azure Speech SDK"""
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            self.speechsdk = speechsdk
            self.speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region
            )
            self.speech_config.speech_synthesis_voice_name = self.voice_name
            self.speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
            )
            
            self.logger.info("azure_tts_initialized", voice=self.voice_name)
            
        except ImportError:
            self.logger.error("azure_speech_not_installed")
            raise RuntimeError("azure-cognitiveservices-speech package not installed")
    
    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        """Stream speech from Azure"""
        try:
            self.logger.info("tts_request", text_length=len(text), provider="azure")
            
            # Create synthesizer with no output (we'll stream manually)
            synthesizer = self.speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=None
            )
            
            # Synthesize
            result = await asyncio.to_thread(
                synthesizer.speak_text,
                text
            )
            
            if result.reason == self.speechsdk.ResultReason.SynthesizingAudioCompleted:
                # Yield audio in chunks
                audio_data = result.audio_data
                chunk_size = 4096
                
                for i in range(0, len(audio_data), chunk_size):
                    yield audio_data[i:i + chunk_size]
                
                self.logger.info("tts_stream_complete", audio_size=len(audio_data))
            else:
                raise RuntimeError(f"Azure TTS failed: {result.reason}")
            
        except Exception as e:
            self.logger.error("tts_stream_failed", error=str(e))
            raise
    
    async def close(self):
        """Close Azure TTS adapter"""
        self.logger.info("tts_closed")


class GTTSFallbackAdapter(TTSAdapter):
    """
    Google Text-to-Speech fallback adapter.
    
    Simple, free TTS for development/testing. Not streaming.
    """
    
    def __init__(self, call_id: str, lang: str = "en"):
        super().__init__(call_id)
        self.lang = lang
        self._setup_client()
    
    def _setup_client(self):
        """Initialize gTTS"""
        try:
            from gtts import gTTS
            self.gTTS = gTTS
            self.logger.info("gtts_fallback_initialized", lang=self.lang)
        except ImportError:
            self.logger.error("gtts_not_installed")
            raise RuntimeError("gtts package not installed")
    
    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        """Generate speech using gTTS (non-streaming)"""
        try:
            self.logger.info("tts_request", text_length=len(text), provider="gtts_fallback")
            
            # Generate speech to temp file
            tts = self.gTTS(text=text, lang=self.lang, slow=False)
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name
            
            await asyncio.to_thread(tts.save, temp_path)
            
            # Convert MP3 to PCM16 using pydub
            from pydub import AudioSegment
            
            audio = await asyncio.to_thread(AudioSegment.from_mp3, temp_path)
            
            # Convert to 16kHz mono PCM16
            audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            
            # Get raw audio data
            raw_audio = audio.raw_data
            
            # Clean up temp file
            os.unlink(temp_path)
            
            # Yield in chunks
            chunk_size = 4096
            for i in range(0, len(raw_audio), chunk_size):
                yield raw_audio[i:i + chunk_size]
                await asyncio.sleep(0.01)  # Small delay to simulate streaming
            
            self.logger.info("tts_stream_complete", audio_size=len(raw_audio))
            
        except Exception as e:
            self.logger.error("tts_fallback_failed", error=str(e))
            raise
    
    async def close(self):
        """Close gTTS fallback adapter"""
        self.logger.info("tts_closed")


class MockTTSAdapter(TTSAdapter):
    """
    Mock TTS adapter for testing.
    
    Generates silent audio or predefined audio chunks.
    """
    
    def __init__(self, call_id: str, audio_duration_ms: int = 2000):
        super().__init__(call_id)
        self.audio_duration_ms = audio_duration_ms
        self.sample_rate = 16000
        self.bytes_per_ms = (self.sample_rate * 2) // 1000  # 16-bit PCM
        self.logger = self.logger.bind(mode="mock")
    
    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        """Generate mock audio (silence)"""
        self.logger.info("mock_tts_request", text_length=len(text))
        
        # Calculate audio size based on text length (rough estimate)
        # ~100ms per character as a simple heuristic
        duration_ms = min(len(text) * 100, self.audio_duration_ms)
        total_bytes = duration_ms * self.bytes_per_ms
        
        # Generate silence in chunks
        chunk_size = 4096
        bytes_sent = 0
        
        while bytes_sent < total_bytes:
            chunk = min(chunk_size, total_bytes - bytes_sent)
            silence = b'\x00' * chunk
            yield silence
            bytes_sent += chunk
            await asyncio.sleep(0.05)  # Simulate streaming delay
        
        self.logger.info("mock_tts_complete", total_bytes=total_bytes)
    
    async def close(self):
        """Close mock TTS"""
        self.logger.info("mock_tts_closed")


def create_tts_adapter(
    call_id: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    use_mock: bool = False
) -> TTSAdapter:
    """
    Factory function to create TTS adapter.
    
    Args:
        call_id: Unique call identifier
        provider: TTS provider ('elevenlabs', 'azure', 'gtts', 'mock')
        api_key: API key for the provider
        voice_id: Voice ID for the provider
        use_mock: If True, returns MockTTSAdapter for testing
        
    Returns:
        TTS adapter instance
    """
    if use_mock:
        return MockTTSAdapter(call_id)
    
    provider = provider or os.getenv("TTS_PROVIDER", "gtts")
    api_key = api_key or os.getenv("TTS_API_KEY")
    voice_id = voice_id or os.getenv("TTS_VOICE_ID")
    
    logger.info("creating_tts_adapter", call_id=call_id, provider=provider)
    
    if provider == "elevenlabs":
        if not api_key:
            logger.warning("elevenlabs_key_missing", message="Using gTTS fallback")
            return GTTSFallbackAdapter(call_id)
        return ElevenLabsTTSAdapter(call_id, api_key, voice_id)
    
    elif provider == "azure":
        subscription_key = api_key
        region = os.getenv("AZURE_SPEECH_REGION", "eastus")
        
        if not subscription_key:
            logger.warning("azure_key_missing", message="Using gTTS fallback")
            return GTTSFallbackAdapter(call_id)
        
        return AzureTTSAdapter(call_id, subscription_key, region, voice_id)
    
    elif provider == "gtts":
        return GTTSFallbackAdapter(call_id)
    
    elif provider == "mock":
        return MockTTSAdapter(call_id)
    
    else:
        logger.warning("unknown_tts_provider", provider=provider, message="Using gTTS fallback")
        return GTTSFallbackAdapter(call_id)
