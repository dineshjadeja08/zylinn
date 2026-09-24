"""
Billing Router — Abstracted Billing Integration
Handles:
  - GET  /billing/plans           — List available subscription plans
  - POST /billing/subscribe       — Create subscription checkout
  - POST /billing/webhook         — Billing webhook (invoice.paid, etc.)
  - GET  /billing/usage           — Current period usage + cost summary
"""
import os
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from providers.billing import get_billing_provider

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# Base plans definition
PLANS = [
    {"id": "starter", "name": "Starter", "price_inr": 2999, "included_minutes": 500, "overage_per_minute_inr": 7},
    {"id": "pro", "name": "Pro", "price_inr": 7999, "included_minutes": 2000, "overage_per_minute_inr": 5},
    {"id": "scale", "name": "Scale", "price_inr": 19999, "included_minutes": 6000, "overage_per_minute_inr": 4},
]

class SubscribeRequest(BaseModel):
    plan_id: str

@router.get("/plans")
async def list_plans():
    return {"plans": PLANS}

@router.post("/subscribe")
async def create_subscription(
    request: SubscribeRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = next((p for p in PLANS if p["id"] == request.plan_id), None)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {request.plan_id}")

    provider = get_billing_provider()
    try:
        result = provider.create_subscription(user, plan, db)
        return result
    except Exception as exc:
        logger.error("checkout_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/webhook")
async def billing_webhook(request: Request, db: Session = Depends(get_db)):
    provider = get_billing_provider()
    try:
        return provider.handle_webhook(request, db)
    except Exception as exc:
        logger.error("webhook_failed", error=str(exc))
        raise HTTPException(status_code=400, detail="Webhook validation failed")

@router.get("/usage")
async def get_usage(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    provider = get_billing_provider()
    return provider.get_usage(user, db)
