import os
from .base import MessagingProvider

def get_messaging_provider() -> MessagingProvider:
    provider_name = os.getenv("MESSAGING_PROVIDER", "meta").lower()
    
    if provider_name == "meta":
        from .meta import MetaMessagingProvider
        return MetaMessagingProvider()
    elif provider_name == "twilio":
        from .twilio import TwilioMessagingProvider
        return TwilioMessagingProvider()
    else:
        raise ValueError(f"Unknown MESSAGING_PROVIDER: {provider_name}")
