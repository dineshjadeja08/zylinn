from abc import ABC, abstractmethod
from typing import Any, Optional


class MessagingProvider(ABC):
    """
    Abstract base class for messaging providers (WhatsApp, SMS, etc.)
    All async methods must be implemented by concrete providers.
    """
    
    @abstractmethod
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
        """Send appointment confirmation. Returns message ID or None on failure."""
        ...
    
    @abstractmethod
    async def send_reminder(
        self,
        to_number: str,
        customer_name: str,
        appointment_date: str,
        appointment_time: str,
        company_name: str,
        call_id: Optional[str] = None,
    ) -> Optional[str]:
        """Send appointment reminder. Returns message ID or None on failure."""
        ...
    
    async def send_call_summary(
        self,
        to_number: str,
        customer_name: str,
        summary: str,
        company_name: str,
        call_id: Optional[str] = None,
    ) -> Optional[str]:
        """Send post-call summary. Default implementation returns None."""
        return None
