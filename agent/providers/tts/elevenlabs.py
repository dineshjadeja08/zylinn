"""
ElevenLabs TTS Provider
"""
import asyncio
import os
from typing import AsyncIterator, Optional
import structlog
from zylinn.agent.providers.tts.base import TTSProvider

logger = structlog.get_logger(__name__)

class ElevenLabsTTSProvider(TTSProvider):
    def __init__(self, call_id: str, api_key: str, voice_id: Optional[str] = None):
        super().__init__(call_id)
        self.api_key = api_key
        self.voice_id = voice_id or "21m00Tcm4TlvDq8ikWAM"
        self._setup_client()
    
    def _setup_client(self):
        try:
            from elevenlabs import generate, stream, Voice
            self.generate_func = generate
            self.stream_func = stream
            self.Voice = Voice
        except ImportError:
            raise RuntimeError("elevenlabs package not installed")
            
    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        try:
            try:
                from elevenlabs.client import ElevenLabs
                client = ElevenLabs(api_key=self.api_key)
                audio_generator = client.generate(
                    text=text,
                    voice=self.voice_id,
                    model="eleven_turbo_v2",
                    stream=True,
                    output_format="pcm_16000"
                )
                for chunk in audio_generator:
                    if chunk:
                        yield chunk
            except ImportError:
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
        except Exception as e:
            raise
            
    async def close(self):
        pass
