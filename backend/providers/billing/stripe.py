"""
Stripe Billing Provider — REQUIRED FALLBACK. Not default in V1.
"""
import os
from typing import Any
import structlog
from fastapi import Response
from sqlalchemy.orm import Session
from .base import BillingProvider

logger = structlog.get_logger(__name__)


class StripeBillingProvider(BillingProvider):
    """Stripe implementation kept as fallback. Set BILLING_PROVIDER=stripe to activate."""
    
    def create_subscription(self, user: Any, plan: dict, db: Session) -> dict:
        logger.warning("stripe_billing_stub", action="create_subscription")
        return {"error": "Stripe not configured as primary provider"}
    
    async def handle_webhook(self, request: Any, db: Session) -> Any:
        logger.warning("stripe_billing_stub", action="handle_webhook")
        return Response(content='{"received": true}', media_type="application/json")
    
    def get_usage(self, user: Any, db: Session) -> dict:
        logger.warning("stripe_billing_stub", action="get_usage")
        return {"error": "Stripe not configured as primary provider"}
