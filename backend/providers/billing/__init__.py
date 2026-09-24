import os
from .base import BillingProvider

def get_billing_provider() -> BillingProvider:
    provider_name = os.getenv("BILLING_PROVIDER", "razorpay").lower()
    
    if provider_name == "razorpay":
        from .razorpay import RazorpayBillingProvider
        return RazorpayBillingProvider()
    elif provider_name == "stripe":
        from .stripe import StripeBillingProvider
        return StripeBillingProvider()
    else:
        raise ValueError(f"Unknown BILLING_PROVIDER: {provider_name}")
