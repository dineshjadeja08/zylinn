"""
Azure TTS Provider
"""
import asyncio
import os
from typing import AsyncIterator, Optional
import structlog
from zylinn.agent.providers.tts.base import TTSProvider

logger = structlog.get_logger(__name__)

class AzureTTSProvider(TTSProvider):
    DEFAULT_TAMIL_VOICE = "ta-IN-PallaviNeural"
    DEFAULT_ENGLISH_VOICE = "en-IN-NeerjaNeural"

    def __init__(self, call_id: str, subscription_key: str, region: str, voice_name: Optional[str] = None, auto_detect_language: bool = True):
        super().__init__(call_id)
        self.subscription_key = subscription_key
        self.region = region
        self.voice_name = voice_name or self.DEFAULT_TAMIL_VOICE
        self.auto_detect_language = auto_detect_language
        self._setup_client()

    def _setup_client(self):
        try:
            import azure.cognitiveservices.speech as speechsdk
            self.speechsdk = speechsdk
            self.speech_config = speechsdk.SpeechConfig(subscription=self.subscription_key, region=self.region)
            self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm)
        except ImportError:
            raise RuntimeError("azure-cognitiveservices-speech not installed")

    def _build_ssml(self, text: str, voice: Optional[str] = None) -> str:
        v = voice or self.voice_name
        lang = "ta-IN" if "Pallavi" in v or "Valluvar" in v else "en-IN"
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
        try:
            ssml = self._build_ssml(text)
            synthesizer = self.speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)
            result = await asyncio.to_thread(synthesizer.speak_ssml, ssml)
            if result.reason == self.speechsdk.ResultReason.SynthesizingAudioCompleted:
                audio_data = result.audio_data
                chunk_size = 4096
                for i in range(0, len(audio_data), chunk_size):
                    yield audio_data[i : i + chunk_size]
            else:
                raise RuntimeError(f"Azure TTS failed: {result.reason}")
        except Exception as exc:
            raise

    async def close(self):
        pass
