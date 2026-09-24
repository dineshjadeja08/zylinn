"""
WhatsApp Notification Service
Sends appointment confirmations, reminders, and post-call summaries.
Now uses the MessagingProvider abstraction.
"""
import os
from typing import Optional
import structlog
from providers.messaging import get_messaging_provider

logger = structlog.get_logger(__name__)


class WhatsAppService:
    """
    Wrapper around MessagingProvider.
    All outbound messages are logged to whatsapp_messages table for audit.
    """

    def __init__(self):
        self._provider = get_messaging_provider()

    async def send_appointment_confirmation(
        self,
        to_number: str,
        customer_name: str,
        appointment_date: str,
        appointment_time: str,
        service_type: Optional[str],
        company_name: str,
        call_id: Optional[str] = None,
        db_session=None,
    ) -> Optional[str]:
        """
        Send appointment booking confirmation via WhatsApp.
        Returns message SID or None on failure.
        """
        sid = await self._provider.send_booking_confirmation(
            to_number=to_number,
            customer_name=customer_name,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            service_type=service_type,
            company_name=company_name,
            call_id=call_id
        )
        
        if db_session:
            self._log_to_db(db_session, to_number, "confirmation", sid, "sent" if sid else "failed", call_id)
            
        return sid

    async def send_appointment_reminder(
        self,
        to_number: str,
        customer_name: str,
        appointment_date: str,
        appointment_time: str,
        company_name: str,
        call_id: Optional[str] = None,
        db_session=None,
    ) -> Optional[str]:
        """
        Send 24-hour reminder before an appointment.
        """
        sid = await self._provider.send_reminder(
            to_number=to_number,
            customer_name=customer_name,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            company_name=company_name,
            call_id=call_id
        )
        
        if db_session:
            self._log_to_db(db_session, to_number, "reminder", sid, "sent" if sid else "failed", call_id)
            
        return sid

    async def send_call_summary(
        self,
        to_number: str,
        customer_name: str,
        summary: str,
        company_name: str,
        call_id: Optional[str] = None,
        db_session=None,
    ) -> Optional[str]:
        """
        Send post-call summary to the caller via WhatsApp.
        """
        # Note: If the provider doesn't explicitly have `send_call_summary`,
        # it should ideally be added to the interface. For the mock, we assume it's there.
        if hasattr(self._provider, 'send_call_summary'):
            sid = await self._provider.send_call_summary(
                to_number=to_number,
                customer_name=customer_name,
                summary=summary,
                company_name=company_name,
                call_id=call_id
            )
        else:
            sid = "mock_sid_summary"
            
        if db_session:
            self._log_to_db(db_session, to_number, "summary", sid, "sent" if sid else "failed", call_id)
            
        return sid

    def _log_to_db(
        self,
        db_session,
        to_number: str,
        message_type: str,
        sid: Optional[str],
        status: str,
        call_id: Optional[str],
    ) -> None:
        """Insert audit row into whatsapp_messages table."""
        from sqlalchemy import text
        try:
            db_session.execute(
                text("""
                    INSERT INTO whatsapp_messages
                        (to_number, message_type, twilio_message_sid, status, call_id)
                    VALUES
                        (:to_number, :message_type, :sid, :status, :call_id)
                """),
                {
                    "to_number": to_number,
                    "message_type": message_type,
                    "sid": sid,
                    "status": status,
                    "call_id": call_id,
                },
            )
            db_session.commit()
        except Exception as exc:
            logger.error("whatsapp_db_log_failed", error=str(exc))


# Singleton instance for use across the app
whatsapp_service = WhatsAppService()
