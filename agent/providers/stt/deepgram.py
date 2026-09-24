"""
Deepgram Nova-2 Streaming STT Provider
"""
import asyncio
import os
from typing import AsyncIterator, List, Optional
import structlog
from zylinn.agent.providers.stt.base import STTProvider, TranscriptResult, TranscriptType

logger = structlog.get_logger(__name__)

class DeepgramSTTProvider(STTProvider):
    SUPPORTED_LANGUAGES = {"en", "ta", "hi", "te", "kn", "ml"}

    def __init__(self, call_id: str, api_key: str, languages: Optional[List[str]] = None, model: str = "nova-2", sample_rate: int = 16_000):
        super().__init__(call_id)
        self.api_key = api_key
        self.languages = languages or ["en"]
        self.model = model
        self.sample_rate = sample_rate
        self.transcript_queue: asyncio.Queue = asyncio.Queue()
        self._connection = None
        self._connected = False
        self._setup_client()

    def _setup_client(self):
        try:
            from deepgram import DeepgramClient, LiveOptions
            self.logger.info("deepgram_stt_ready", languages=self.languages, model=self.model)
        except ImportError:
            self.logger.error("deepgram_sdk_not_installed")
            raise RuntimeError("deepgram-sdk not installed")

    async def _ensure_connected(self):
        if self._connected:
            return
        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
        dg_client = DeepgramClient(self.api_key)
        detect_language = len(self.languages) > 1
        primary_language = self.languages[0] if self.languages else "en"
        options = LiveOptions(
            model=self.model,
            language=primary_language if not detect_language else None,
            detect_language=detect_language,
            smart_format=True,
            interim_results=True,
            utterance_end_ms=1000,
            vad_events=True,
            encoding="linear16",
            sample_rate=self.sample_rate,
            channels=1,
        )
        self._connection = dg_client.listen.asyncwebsocket.v("1")

        async def on_message(self_inner, result, **kwargs):
            try:
                sentence = result.channel.alternatives[0].transcript
                if not sentence:
                    return
                is_final = result.is_final
                speech_final = getattr(result, "speech_final", False)
                detected_lang = getattr(result.channel.alternatives[0], "languages", [primary_language])
                confidence = getattr(result.channel.alternatives[0], "confidence", 0.9)
                transcript_result = TranscriptResult(
                    text=sentence,
                    is_final=is_final or speech_final,
                    confidence=float(confidence),
                    timestamp=asyncio.get_event_loop().time(),
                    type=TranscriptType.FINAL if (is_final or speech_final) else TranscriptType.PARTIAL,
                    detected_languages=detected_lang
                )
                await self.transcript_queue.put(transcript_result)
            except Exception as exc:
                self.logger.error("deepgram_on_message_error", error=str(exc))

        async def on_error(self_inner, error, **kwargs):
            self.logger.error("deepgram_websocket_error", error=str(error))

        async def on_close(self_inner, close, **kwargs):
            self._connected = False

        self._connection.on(LiveTranscriptionEvents.Transcript, on_message)
        self._connection.on(LiveTranscriptionEvents.Error, on_error)
        self._connection.on(LiveTranscriptionEvents.Close, on_close)

        await self._connection.start(options)
        self._connected = True

    async def send_audio_chunk(self, audio_data: bytes):
        if not audio_data:
            return
        try:
            await self._ensure_connected()
            await self._connection.send(audio_data)
        except Exception as exc:
            self._connected = False
            raise

    async def get_transcript_stream(self) -> AsyncIterator[TranscriptResult]:
        while True:
            try:
                result = await asyncio.wait_for(self.transcript_queue.get(), timeout=60.0)
                yield result
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1.0)
                continue

    async def reset(self):
        while not self.transcript_queue.empty():
            self.transcript_queue.get_nowait()

    async def close(self):
        if self._connection and self._connected:
            try:
                await self._connection.finish()
            except Exception:
                pass
            self._connected = False
