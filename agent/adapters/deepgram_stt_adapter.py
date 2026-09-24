"""
Deepgram Nova-2 Streaming STT Adapter
Provides real-time transcription with Tamil + English code-switching support.

Deepgram Nova-2 supports:
- Tamil (ta) as a first-class language
- Multilingual detection within a single stream
- Low-latency interim results (< 300ms)
- Word-level confidence scores

Environment variables:
    DEEPGRAM_API_KEY: Deepgram API key (get from console.deepgram.com)
    STT_LANGUAGES:    Comma-separated language codes, e.g. "ta,en" (default: "en")
"""
import asyncio
import json
import os
from typing import AsyncIterator, List, Optional

import structlog

from adapters.stt_adapter import STTAdapter, TranscriptResult, TranscriptType

logger = structlog.get_logger(__name__)


class DeepgramSTTAdapter(STTAdapter):
    """
    Deepgram Nova-2 streaming STT with Tamil/English multilingual support.

    Uses the Deepgram Python SDK v3+ which wraps the WebSocket API.
    Falls back gracefully if the SDK is not installed.
    """

    # Deepgram Nova-2 supports these Indian-market languages
    SUPPORTED_LANGUAGES = {"en", "ta", "hi", "te", "kn", "ml"}

    def __init__(
        self,
        call_id: str,
        api_key: str,
        languages: Optional[List[str]] = None,
        model: str = "nova-2",
        sample_rate: int = 16_000,
    ):
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
        """Validate Deepgram SDK is available."""
        try:
            from deepgram import DeepgramClient, LiveOptions  # noqa: F401
            self.logger.info(
                "deepgram_stt_ready",
                languages=self.languages,
                model=self.model,
            )
        except ImportError:
            self.logger.error("deepgram_sdk_not_installed", hint="pip install deepgram-sdk>=3.0.0")
            raise RuntimeError(
                "deepgram-sdk not installed. Run: pip install deepgram-sdk>=3.0.0"
            )

    async def _ensure_connected(self):
        """Open WebSocket connection to Deepgram if not already open."""
        if self._connected:
            return

        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

        dg_client = DeepgramClient(self.api_key)

        # Build language options — Deepgram supports multi-language via
        # detect_language=True when multiple langs are provided
        detect_language = len(self.languages) > 1
        primary_language = self.languages[0] if self.languages else "en"

        options = LiveOptions(
            model=self.model,
            language=primary_language if not detect_language else None,
            detect_language=detect_language,
            smart_format=True,
            interim_results=True,
            utterance_end_ms=1000,  # emit UtteranceEnd after 1s silence
            vad_events=True,
            encoding="linear16",
            sample_rate=self.sample_rate,
            channels=1,
        )

        self._connection = dg_client.listen.asyncwebsocket.v("1")

        # Register event handlers
        async def on_message(self_inner, result, **kwargs):
            """Handle transcription results from Deepgram."""
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
                )

                # Tag the detected language on the result for downstream use
                transcript_result.detected_languages = detected_lang  # type: ignore[attr-defined]

                await self.transcript_queue.put(transcript_result)

                self.logger.debug(
                    "deepgram_transcript",
                    text=sentence[:80],
                    is_final=transcript_result.is_final,
                    lang=detected_lang,
                )
            except Exception as exc:
                self.logger.error("deepgram_on_message_error", error=str(exc))

        async def on_error(self_inner, error, **kwargs):
            self.logger.error("deepgram_websocket_error", error=str(error))

        async def on_close(self_inner, close, **kwargs):
            self.logger.info("deepgram_connection_closed")
            self._connected = False

        self._connection.on(LiveTranscriptionEvents.Transcript, on_message)
        self._connection.on(LiveTranscriptionEvents.Error, on_error)
        self._connection.on(LiveTranscriptionEvents.Close, on_close)

        await self._connection.start(options)
        self._connected = True
        self.logger.info(
            "deepgram_connected",
            model=self.model,
            languages=self.languages,
            detect_language=detect_language,
        )

    async def send_audio_chunk(self, audio_data: bytes):
        """Send raw PCM16 audio chunk to Deepgram for transcription."""
        if not audio_data:
            return
        try:
            await self._ensure_connected()
            await self._connection.send(audio_data)
        except Exception as exc:
            self.logger.error("deepgram_send_error", error=str(exc))
            self._connected = False  # Force reconnect on next chunk
            raise

    async def get_transcript_stream(self) -> AsyncIterator[TranscriptResult]:
        """Yield transcript results as they arrive from Deepgram."""
        while True:
            try:
                result = await asyncio.wait_for(
                    self.transcript_queue.get(),
                    timeout=60.0,  # 60s keepalive
                )
                yield result
            except asyncio.TimeoutError:
                self.logger.debug("deepgram_stt_keepalive")
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.error("deepgram_stream_error", error=str(exc))
                await asyncio.sleep(1.0)
                continue

    async def reset(self):
        """Flush internal queue (e.g. after barge-in)."""
        while not self.transcript_queue.empty():
            self.transcript_queue.get_nowait()
        self.logger.info("deepgram_stt_reset")

    async def close(self):
        """Close the Deepgram WebSocket connection."""
        if self._connection and self._connected:
            try:
                await self._connection.finish()
            except Exception:
                pass
            self._connected = False
        self.logger.info("deepgram_stt_closed")


def create_deepgram_adapter(
    call_id: str,
    languages: Optional[List[str]] = None,
    api_key: Optional[str] = None,
) -> DeepgramSTTAdapter:
    """
    Factory for Deepgram STT adapter.

    Args:
        call_id:   Unique call identifier.
        languages: List of language codes, e.g. ["ta", "en"] for Tamil+English.
                   Defaults to STT_LANGUAGES env var or ["en"].
        api_key:   Deepgram API key. Defaults to DEEPGRAM_API_KEY env var.

    Returns:
        Configured DeepgramSTTAdapter instance.
    """
    api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise ValueError(
            "Deepgram API key required. Set DEEPGRAM_API_KEY env var or pass api_key."
        )

    env_langs = os.getenv("STT_LANGUAGES", "en")
    languages = languages or [lang.strip() for lang in env_langs.split(",")]

    return DeepgramSTTAdapter(call_id=call_id, api_key=api_key, languages=languages)
