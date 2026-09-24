"""
Sarvam STT Provider — Saaras Streaming API
Docs: https://docs.sarvam.ai/api-reference-docs/speech-to-text-translate/streaming
"""
import os
import json
import asyncio
import base64
from typing import AsyncGenerator
import structlog
from providers.stt.base import STTProvider

logger = structlog.get_logger(__name__)

SARVAM_STT_WS_URL = "wss://api.sarvam.ai/speech-to-text-translate/streaming"

class SarvamSTTProvider(STTProvider):
    def __init__(self, call_id: str, languages: list, api_key: str = None):
        self.call_id = call_id
        self.languages = languages
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is required. Set it in your .env file.")
        self._ws = None
        self._connected = False
        self._transcript_queue: asyncio.Queue = asyncio.Queue()
        self._closed = False
        self.logger = logger.bind(call_id=call_id)
        
    async def connect(self):
        """Open a WebSocket connection to Sarvam Saaras streaming STT."""
        try:
            import websockets
        except ImportError:
            raise RuntimeError("websockets package not installed. Run: pip install websockets>=12.0")
        
        # Sarvam uses language codes like 'ta-IN', 'en-IN'
        lang_map = {"ta": "ta-IN", "en": "en-IN", "hi": "hi-IN"}
        language_code = lang_map.get(self.languages[0], "ta-IN") if self.languages else "ta-IN"
        
        headers = {
            "api-subscription-key": self.api_key,
        }
        params = f"?language_code={language_code}&model=saaras:v1"
        url = SARVAM_STT_WS_URL + params
        
        self._ws = await websockets.connect(url, extra_headers=headers)
        self._connected = True
        self.logger.info("sarvam_stt_connected", language=language_code)
        
        # Start background receiver task
        asyncio.create_task(self._receive_loop())
    
    async def _receive_loop(self):
        """Background task: receive transcript events from Sarvam WS."""
        try:
            async for raw_msg in self._ws:
                if self._closed:
                    break
                try:
                    msg = json.loads(raw_msg)
                    # Sarvam returns {"transcript": "...", "is_final": true/false}
                    if "transcript" in msg:
                        transcript = {
                            "text": msg.get("transcript", ""),
                            "is_final": msg.get("is_final", False),
                            "confidence": msg.get("confidence", 1.0),
                            "language": msg.get("language_code", "ta-IN"),
                        }
                        await self._transcript_queue.put(transcript)
                except Exception as exc:
                    self.logger.error("sarvam_stt_parse_error", error=str(exc))
        except Exception as exc:
            if not self._closed:
                self.logger.error("sarvam_stt_receive_error", error=str(exc))
        finally:
            await self._transcript_queue.put(None)  # Signal end
    
    async def send_audio(self, pcm_data: bytes):
        """Send PCM16 audio bytes to Sarvam STT."""
        if not self._connected or not self._ws:
            raise RuntimeError("Call connect() before sending audio")
        try:
            # Sarvam expects base64-encoded audio in JSON envelope
            audio_b64 = base64.b64encode(pcm_data).decode()
            await self._ws.send(json.dumps({"audio": audio_b64}))
        except Exception as exc:
            self.logger.error("sarvam_stt_send_error", error=str(exc))
    
    async def receive_transcripts(self) -> AsyncGenerator[dict, None]:
        """Yield transcript dicts from Sarvam until closed."""
        while True:
            item = await self._transcript_queue.get()
            if item is None:  # End signal
                break
            yield item
    
    async def close(self):
        """Close the STT connection."""
        self._closed = True
        self._connected = False
        if self._ws:
            try:
                # Send end-of-stream signal
                await self._ws.send(json.dumps({"end_of_stream": True}))
                await self._ws.close()
            except Exception:
                pass
        self.logger.info("sarvam_stt_closed")
