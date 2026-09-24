"""
Sarvam TTS Provider — Bulbul v2 REST API
Docs: https://docs.sarvam.ai/api-reference-docs/text-to-speech
"""
import os
import json
import asyncio
import base64
from typing import AsyncGenerator
import structlog
from providers.tts.base import TTSProvider

logger = structlog.get_logger(__name__)

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

# Language to speaker mapping for Sarvam Bulbul
LANG_TO_SPEAKER = {
    "ta-IN": "arvind",   # Tamil male  
    "en-IN": "meera",   # Indian English female
    "hi-IN": "meera",   # Hindi female
}

class SarvamTTSProvider(TTSProvider):
    def __init__(self, call_id: str = None, api_key: str = None):
        self.call_id = call_id
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is required. Set it in your .env file.")
        self.logger = logger.bind(call_id=call_id or "unknown")
    
    async def synthesize(self, text: str, language: str = "ta-IN", voice_id: str = None) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to speech using Sarvam Bulbul API.
        Yields audio chunks as bytes (WAV/PCM).
        """
        try:
            import aiohttp
        except ImportError:
            raise RuntimeError("aiohttp not installed. Run: pip install aiohttp>=3.9")
        
        # Map short lang code to full BCP-47
        lang_map = {"ta": "ta-IN", "en": "en-IN", "hi": "hi-IN"}
        lang_code = lang_map.get(language, language)
        speaker = voice_id or LANG_TO_SPEAKER.get(lang_code, "meera")
        
        payload = {
            "inputs": [text],
            "target_language_code": lang_code,
            "speaker": speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.5,
            "speech_sample_rate": 16000,
            "enable_preprocessing": True,
            "model": "bulbul:v1",
        }
        
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }
        
        import time
        start = time.time()
        
        async with aiohttp.ClientSession() as session:
            async with session.post(SARVAM_TTS_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    self.logger.error("sarvam_tts_error", status=resp.status, body=body[:200])
                    raise RuntimeError(f"Sarvam TTS failed: {resp.status} {body[:100]}")
                
                data = await resp.json()
                
        first_audio_ms = (time.time() - start) * 1000
        self.logger.info("sarvam_tts_response", first_audio_ms=first_audio_ms, chars=len(text))
        
        # Sarvam returns base64-encoded audio per input
        audios = data.get("audios", [])
        if not audios:
            raise RuntimeError("Sarvam TTS returned no audio")
        
        audio_b64 = audios[0]
        audio_bytes = base64.b64decode(audio_b64)
        
        # Yield in 4KB chunks for streaming
        CHUNK_SIZE = 4096
        for i in range(0, len(audio_bytes), CHUNK_SIZE):
            yield audio_bytes[i:i + CHUNK_SIZE]
            await asyncio.sleep(0)  # yield control to event loop
