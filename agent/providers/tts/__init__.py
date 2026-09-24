import os
from .base import TTSProvider

def get_tts_provider(call_id: str) -> TTSProvider:
    provider_name = os.getenv("TTS_PROVIDER", "sarvam").lower()
    
    if provider_name == "sarvam":
        from .sarvam import SarvamTTSProvider
        return SarvamTTSProvider()
    elif provider_name == "azure":
        from .azure import AzureTTSProvider
        return AzureTTSProvider(call_id=call_id)
    elif provider_name == "elevenlabs":
        from .elevenlabs import ElevenLabsTTSProvider
        return ElevenLabsTTSProvider(call_id=call_id)
    else:
        raise ValueError(f"Unknown TTS_PROVIDER: {provider_name}")
