"""
Meta WhatsApp Cloud API Messaging Provider.
Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/

Env vars required:
  META_WHATSAPP_TOKEN
  META_PHONE_NUMBER_ID
"""
import os
from typing import Optional
import structlog
from .base import MessagingProvider

logger = structlog.get_logger(__name__)

META_API_URL = "https://graph.facebook.com/v19.0"


class MetaMessagingProvider(MessagingProvider):
    def __init__(self):
        self.token = os.getenv("META_WHATSAPP_TOKEN", "")
        self.phone_number_id = os.getenv("META_PHONE_NUMBER_ID", "")
        
        if not self.token and os.getenv("ENVIRONMENT", "development") == "production":
            raise ValueError("META_WHATSAPP_TOKEN required in production.")
    
    def _format_number(self, phone: str) -> str:
        """Normalize phone number to E.164 without + prefix for Meta API."""
        phone = phone.strip().lstrip("+")
        if phone.startswith("91") and len(phone) == 12:
            return phone
        if len(phone) == 10:
            return f"91{phone}"
        return phone
    
    async def _send_text(
        self,
        to_number: str,
        body: str,
        message_type: str,
        call_id: Optional[str],
    ) -> Optional[str]:
        """Send a free-form text message via Meta Cloud API."""
        try:
            import aiohttp
        except ImportError:
            raise RuntimeError("aiohttp not installed.")
        
        if not self.token or not self.phone_number_id:
            logger.warning("meta_whatsapp_credentials_missing", message_type=message_type)
            return None
        
        to = self._format_number(to_number)
        url = f"{META_API_URL}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status == 200:
                    msg_id = data.get("messages", [{}])[0].get("id")
                    logger.info("meta_whatsapp_sent", to=to, message_type=message_type, msg_id=msg_id, call_id=call_id)
                    return msg_id
                else:
                    logger.error("meta_whatsapp_failed", status=resp.status, body=str(data)[:200], call_id=call_id)
                    return None
    
    async def send_booking_confirmation(
        self,
        to_number: str,
        customer_name: str,
        appointment_date: str,
        appointment_time: str,
        service_type: Optional[str],
        company_name: str,
        call_id: Optional[str] = None,
    ) -> Optional[str]:
        service_line = f"\n📋 Service: {service_type}" if service_type else ""
        body = (
            f"✅ *Appointment Confirmed!*\n\n"
            f"Hello {customer_name},\n"
            f"Your appointment with *{company_name}* is confirmed.\n\n"
            f"📅 Date: {appointment_date}\n"
            f"🕐 Time: {appointment_time}"
            f"{service_line}\n\n"
            f"To reschedule or cancel, please call us back. 🙏"
        )
        return await self._send_text(to_number, body, "confirmation", call_id)
    
    async def send_reminder(
        self,
        to_number: str,
        customer_name: str,
        appointment_date: str,
        appointment_time: str,
        company_name: str,
        call_id: Optional[str] = None,
    ) -> Optional[str]:
        body = (
            f"⏰ *Appointment Reminder*\n\n"
            f"Hello {customer_name},\n"
            f"Reminder: Appointment with *{company_name}* tomorrow.\n\n"
            f"📅 Date: {appointment_date}\n"
            f"🕐 Time: {appointment_time}\n\n"
            f"Need to reschedule? Please call us today. 😊"
        )
        return await self._send_text(to_number, body, "reminder", call_id)
    
    async def send_call_summary(
        self,
        to_number: str,
        customer_name: str,
        summary: str,
        company_name: str,
        call_id: Optional[str] = None,
    ) -> Optional[str]:
        body = (
            f"📞 *Call Summary from {company_name}*\n\n"
            f"Hello {customer_name},\n"
            f"Thank you for calling!\n\n"
            f"{summary}\n\n"
            f"Questions? Feel free to call us again. 🙏"
        )
        return await self._send_text(to_number, body, "summary", call_id)
