from abc import ABC, abstractmethod
from typing import Any, Optional
from sqlalchemy.orm import Session


class BillingProvider(ABC):
    """Abstract base for billing providers (Razorpay, Stripe)."""
    
    @abstractmethod
    def create_subscription(self, user: Any, plan: dict, db: Session) -> dict:
        """Create a subscription/checkout session. Returns dict with checkout_url."""
        ...
    
    @abstractmethod
    async def handle_webhook(self, request: Any, db: Session) -> Any:
        """Handle billing webhook event. Returns FastAPI Response."""
        ...
    
    @abstractmethod
    def get_usage(self, user: Any, db: Session) -> dict:
        """Return current billing period usage and cost."""
        ...
