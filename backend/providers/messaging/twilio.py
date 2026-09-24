from typing import Any, Optional
from .base import MessagingProvider
import os
import structlog

logger = structlog.get_logger(__name__)

class TwilioMessagingProvider(MessagingProvider):
    """Twilio WhatsApp — REQUIRED FALLBACK. Not default in V1."""
    
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_WHATSAPP_FROM", "")
    
    async def send_booking_confirmation(self, to_number, customer_name, appointment_date, appointment_time, service_type, company_name, call_id=None):
        logger.warning("twilio_messaging_stub", action="send_booking_confirmation")
        return None
    
    async def send_reminder(self, to_number, customer_name, appointment_date, appointment_time, company_name, call_id=None):
        logger.warning("twilio_messaging_stub", action="send_reminder")
        return None
