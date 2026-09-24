"""
Razorpay Billing Provider.
Docs: https://razorpay.com/docs/api/

Env vars:
  RAZORPAY_KEY_ID
  RAZORPAY_KEY_SECRET
  RAZORPAY_WEBHOOK_SECRET
  RAZORPAY_PLAN_STARTER, RAZORPAY_PLAN_PRO, RAZORPAY_PLAN_SCALE
  FRONTEND_URL
"""
import hashlib
import hmac
import json
import os
from typing import Any
import structlog
from fastapi import Response
from sqlalchemy import text
from sqlalchemy.orm import Session
from .base import BillingProvider

logger = structlog.get_logger(__name__)

PLAN_MAP = {
    "starter": {"plan_env": "RAZORPAY_PLAN_STARTER", "included_minutes": 500, "overage_rate": 7},
    "pro":     {"plan_env": "RAZORPAY_PLAN_PRO",     "included_minutes": 2000, "overage_rate": 5},
    "scale":   {"plan_env": "RAZORPAY_PLAN_SCALE",   "included_minutes": 6000, "overage_rate": 4},
}


class RazorpayBillingProvider(BillingProvider):
    def __init__(self):
        self.key_id = os.getenv("RAZORPAY_KEY_ID", "")
        self.key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        self.webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        if not self.key_id and os.getenv("ENVIRONMENT", "development") == "production":
            raise ValueError("RAZORPAY_KEY_ID required in production.")
    
    def _get_client(self):
        try:
            import razorpay
            return razorpay.Client(auth=(self.key_id, self.key_secret))
        except ImportError:
            raise RuntimeError("razorpay SDK not installed. Run: pip install razorpay")
    
    def create_subscription(self, user: Any, plan: dict, db: Session) -> dict:
        plan_id = plan["id"]
        plan_meta = PLAN_MAP.get(plan_id)
        
        if not plan_meta:
            raise ValueError(f"Unknown plan: {plan_id}")
        
        razorpay_plan_id = os.getenv(plan_meta["plan_env"], "")
        if not razorpay_plan_id:
            if os.getenv("ENVIRONMENT", "development") == "production":
                raise RuntimeError(f"{plan_meta['plan_env']} not configured")
            # Dev mode: return mock checkout
            logger.warning("razorpay_dev_mode_mock_checkout", plan=plan_id)
            return {
                "checkout_url": f"{self.frontend_url}/dashboard/billing?mock_checkout=1&plan={plan_id}",
                "provider": "razorpay",
                "note": "Mock checkout — set RAZORPAY_PLAN_* in .env for real payments",
            }
        
        client = self._get_client()
        subscription = client.subscription.create({
            "plan_id": razorpay_plan_id,
            "total_count": 12,
            "quantity": 1,
            "customer_notify": 1,
            "notes": {"customer_id": str(getattr(user, "customer_id", ""))},
        })
        
        logger.info("razorpay_subscription_created", sub_id=subscription["id"], plan=plan_id)
        
        checkout_url = f"https://api.razorpay.com/v1/checkout/embedded?subscription_id={subscription['id']}&key={self.key_id}"
        return {"checkout_url": checkout_url, "subscription_id": subscription["id"]}
    
    async def handle_webhook(self, request: Any, db: Session) -> Any:
        """Verify Razorpay webhook signature and process events."""
        payload = await request.body()
        sig_header = request.headers.get("x-razorpay-signature", "")
        
        if self.webhook_secret:
            expected = hmac.new(
                self.webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(expected, sig_header):
                logger.error("razorpay_webhook_invalid_signature")
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Invalid signature")
        
        event = json.loads(payload)
        event_type = event.get("event", "")
        logger.info("razorpay_webhook", event_type=event_type)
        
        if event_type == "subscription.activated":
            sub = event["payload"]["subscription"]["entity"]
            customer_id = sub.get("notes", {}).get("customer_id")
            plan_id_rz = sub.get("plan_id", "")
            # Map Razorpay plan_id back to our plan name
            plan_name = next(
                (k for k, v in PLAN_MAP.items() if os.getenv(v["plan_env"], "") == plan_id_rz),
                "starter"
            )
            if customer_id:
                db.execute(
                    text("UPDATE customers SET plan_type = :plan WHERE customer_id = :cid"),
                    {"plan": plan_name, "cid": customer_id}
                )
                db.commit()
                logger.info("subscription_activated", customer_id=customer_id, plan=plan_name)
        
        return Response(content='{"received": true}', media_type="application/json")
    
    def get_usage(self, user: Any, db: Session) -> dict:
        from sqlalchemy import text
        row = db.execute(
            text("""
                SELECT c.calls_this_month, c.max_calls_per_month, c.plan_type,
                       COALESCE(SUM(u.cost_usd), 0) as total_cost,
                       COALESCE(SUM(u.duration_seconds), 0) as total_secs
                FROM customers c
                LEFT JOIN usage_logs u ON u.customer_id = c.customer_id
                    AND u.created_at >= date_trunc('month', NOW())
                WHERE c.customer_id = :cid
                GROUP BY c.calls_this_month, c.max_calls_per_month, c.plan_type
            """),
            {"cid": str(getattr(user, "customer_id", ""))}
        ).fetchone()
        
        if not row:
            return {"error": "customer not found"}
        
        plan_meta = PLAN_MAP.get(row[2] or "starter", PLAN_MAP["starter"])
        total_mins = float(row[4]) / 60
        overage = max(0, total_mins - plan_meta["included_minutes"])
        
        return {
            "plan": row[2],
            "calls_this_month": row[0],
            "max_calls_per_month": row[1],
            "minutes_used": round(total_mins, 2),
            "minutes_included": plan_meta["included_minutes"],
            "overage_minutes": round(overage, 2),
            "overage_cost_inr": round(overage * plan_meta["overage_rate"], 2),
            "total_cost_usd_this_month": round(float(row[3]), 4),
        }
