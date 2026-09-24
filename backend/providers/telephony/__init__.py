import os
from .base import TelephonyProvider

def get_telephony_provider() -> TelephonyProvider:
    provider_name = os.getenv("TELEPHONY_PROVIDER", "exotel").lower()
    
    if provider_name == "exotel":
        from .exotel import ExotelTelephonyProvider
        return ExotelTelephonyProvider()
    elif provider_name == "twilio":
        from .twilio import TwilioTelephonyProvider
        return TwilioTelephonyProvider()
    else:
        raise ValueError(f"Unknown TELEPHONY_PROVIDER: {provider_name}")
