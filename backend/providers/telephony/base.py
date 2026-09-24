from abc import ABC, abstractmethod
from typing import Any, Dict

class TelephonyProvider(ABC):
    @abstractmethod
    def handle_incoming(self, request_data: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def transfer_call(self, call_sid: str, target_number: str) -> Any:
        pass

    @abstractmethod
    def end_call(self, call_sid: str) -> Any:
        pass
