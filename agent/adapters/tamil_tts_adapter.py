"""
Tamil-aware TTS Adapter
Extends the existing TTS adapter factory to support Tamil voice routing.

Tamil voice recommendations:
  - Azure: ta-IN-PallaviNeural (female), ta-IN-ValluvarNeural (male)
  - ElevenLabs: No native Tamil — use Azure for Tamil segments
  - gTTS: Supports Tamil (lang='ta') as fallback

Voice routing strategy:
  If the detected_language of the transcript is 'ta':
    → Use Azure TTS with ta-IN-PallaviNeural
  Else:
    → Use ElevenLabs (or configured default)
"""
import asyncio
import os
from typing import AsyncIterator, Optional

import structlog

from adapters.tts_adapter import TTSAdapter, MockTTSAdapter

logger = structlog.get_logger(__name__)


class AzureTamilTTSAdapter(TTSAdapter):
    """
    Azure TTS adapter configured specifically for Tamil and Tamil-English code-switch.

    Uses Azure Neural TTS which handles Tamil Unicode text correctly.
    Voice: ta-IN-PallaviNeural (female) by default.
    Output: PCM 16kHz mono, ready for LiveKit.
    """

    DEFAULT_TAMIL_VOICE = "ta-IN-PallaviNeural"
    DEFAULT_ENGLISH_VOICE = "en-IN-NeerjaNeural"  # Indian English for consistency

    def __init__(
        self,
        call_id: str,
        subscription_key: str,
        region: str,
        voice_name: Optional[str] = None,
        auto_detect_language: bool = True,
    ):
        super().__init__(call_id)
        self.subscription_key = subscription_key
        self.region = region
        self.voice_name = voice_name or self.DEFAULT_TAMIL_VOICE
        self.auto_detect_language = auto_detect_language
        self._setup_client()

    def _setup_client(self):
        """Initialise Azure Speech SDK."""
        try:
            import azure.cognitiveservices.speech as speechsdk

            self.speechsdk = speechsdk
            self.speech_config = speechsdk.SpeechConfig(
                subscription=self.subscription_key,
                region=self.region,
            )
            # PCM 16kHz mono — matches LiveKit's expected format
            self.speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm
            )
            self.logger.info("azure_tamil_tts_ready", voice=self.voice_name, region=self.region)
        except ImportError:
            self.logger.error("azure_speech_sdk_missing", hint="pip install azure-cognitiveservices-speech")
            raise RuntimeError("azure-cognitiveservices-speech not installed")

    def _build_ssml(self, text: str, voice: Optional[str] = None) -> str:
        """
        Build SSML for Tamil-English code-switch.

        Azure supports <lang xml:lang="ta-IN"> within SSML for inline language switching.
        This ensures Tamil segments use the Tamil voice even in a mixed utterance.
        """
        from adapters.language_config import detect_language_from_text

        v = voice or self.voice_name
        lang = "ta-IN" if "Pallavi" in v or "Valluvar" in v else "en-IN"

        if self.auto_detect_language:
            detected = detect_language_from_text(text)
            if detected == "ta":
                lang = "ta-IN"
                v = self.DEFAULT_TAMIL_VOICE

        return (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{lang}">'
            f'<voice name="{v}">'
            f'<mstts:express-as style="customerservice">'
            f"{text}"
            f"</mstts:express-as>"
            f"</voice>"
            f"</speak>"
        )

    async def stream_speech(self, text: str) -> AsyncIterator[bytes]:
        """Synthesise speech from text and stream PCM16 chunks."""
        try:
            self.logger.info("azure_tts_request", text_length=len(text), voice=self.voice_name)

            ssml = self._build_ssml(text)

            synthesizer = self.speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=None,
            )

            result = await asyncio.to_thread(synthesizer.speak_ssml, ssml)

            if result.reason == self.speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio_data = result.audio_data
                chunk_size = 4096
                for i in range(0, len(audio_data), chunk_size):
                    yield audio_data[i : i + chunk_size]
                self.logger.info("azure_tts_complete", audio_bytes=len(audio_data))
            else:
                cancellation = self.speechsdk.CancellationDetails.from_result(result)
                raise RuntimeError(
                    f"Azure TTS failed: reason={result.reason}, "
                    f"error={cancellation.error_details}"
                )
        except Exception as exc:
            self.logger.error("azure_tts_error", error=str(exc))
            raise

    async def close(self):
        self.logger.info("azure_tamil_tts_closed")


class SmartTTSRouter:
    """
    Routes TTS to the appropriate provider based on detected language.

    Strategy:
      - Tamil text  → Azure TTS (ta-IN-PallaviNeural)
      - English text → ElevenLabs or configured default
      - Mixed text   → Azure TTS (handles code-switch via SSML)

    This avoids ElevenLabs trying to speak Tamil phonetically (sounds wrong).
    """

    def __init__(
        self,
        call_id: str,
        azure_key: Optional[str] = None,
        azure_region: Optional[str] = None,
        elevenlabs_key: Optional[str] = None,
        elevenlabs_voice_id: Optional[str] = None,
        use_mock: bool = False,
    ):
        self.call_id = call_id
        self.use_mock = use_mock
        self.logger = logger.bind(call_id=call_id)

        if use_mock:
            self._tamil_adapter = MockTTSAdapter(call_id)
            self._english_adapter = MockTTSAdapter(call_id)
            return

        # Tamil adapter (Azure)
        azure_key = azure_key or os.getenv("AZURE_SPEECH_KEY")
        azure_region = azure_region or os.getenv("AZURE_SPEECH_REGION", "eastus")
        if azure_key:
            self._tamil_adapter = AzureTamilTTSAdapter(call_id, azure_key, azure_region)
        else:
            self.logger.warning("azure_key_missing_fallback_gtts")
            from adapters.tts_adapter import GTTSFallbackAdapter
            self._tamil_adapter = GTTSFallbackAdapter(call_id, lang="ta")

        # English adapter (ElevenLabs preferred)
        elevenlabs_key = elevenlabs_key or os.getenv("TTS_API_KEY") or os.getenv("ELEVENLABS_API_KEY")
        if elevenlabs_key:
            from adapters.tts_adapter import ElevenLabsTTSAdapter
            self._english_adapter = ElevenLabsTTSAdapter(
                call_id, elevenlabs_key, elevenlabs_voice_id or os.getenv("TTS_VOICE_ID")
            )
        else:
            self.logger.warning("elevenlabs_key_missing_fallback_gtts")
            from adapters.tts_adapter import GTTSFallbackAdapter
            self._english_adapter = GTTSFallbackAdapter(call_id, lang="en")

    async def stream_speech(self, text: str, detected_language: str = "en") -> AsyncIterator[bytes]:
        """
        Route TTS based on detected language of the text.

        Args:
            text:              Text to synthesise.
            detected_language: 'ta', 'en', or 'ta-en' (code-switch).
        """
        from adapters.language_config import detect_language_from_text

        # If detected_language not explicit, detect from Unicode content
        if detected_language == "en":
            detected_language = detect_language_from_text(text)

        if detected_language in ("ta", "ta-en"):
            self.logger.debug("tts_routing_tamil", text_preview=text[:40])
            adapter = self._tamil_adapter
        else:
            self.logger.debug("tts_routing_english", text_preview=text[:40])
            adapter = self._english_adapter

        async for chunk in adapter.stream_speech(text):
            yield chunk

    async def close(self):
        await self._tamil_adapter.close()
        await self._english_adapter.close()


def create_smart_tts_router(call_id: str, use_mock: bool = False) -> SmartTTSRouter:
    """
    Factory for the language-aware TTS router.

    Reads all config from environment variables:
        AZURE_SPEECH_KEY, AZURE_SPEECH_REGION
        TTS_API_KEY (ElevenLabs), TTS_VOICE_ID
    """
    return SmartTTSRouter(call_id=call_id, use_mock=use_mock)
