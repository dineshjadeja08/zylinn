import os
from .base import STTProvider

def get_stt_provider(call_id: str, languages: list[str]) -> STTProvider:
    provider_name = os.getenv("STT_PROVIDER", "sarvam").lower()
    
    if provider_name == "sarvam":
        from .sarvam import SarvamSTTProvider
        return SarvamSTTProvider(call_id=call_id, languages=languages)
    elif provider_name == "deepgram":
        from .deepgram import DeepgramSTTAdapter
        # Handle the legacy adapter name if the subagent kept it as DeepgramSTTAdapter
        return DeepgramSTTAdapter(call_id=call_id, languages=languages)
    else:
        raise ValueError(f"Unknown STT_PROVIDER: {provider_name}")
