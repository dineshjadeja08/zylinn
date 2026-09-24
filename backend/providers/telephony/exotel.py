"""
Exotel Telephony Provider
Handles inbound call webhooks from Exotel and bridges to LiveKit.

Exotel webhook POST fields:
  CallSid, From, To, CallStatus, Direction, DialCallStatus, etc.

Docs: https://developer.exotel.com/api/
"""
import asyncio
import hmac
import hashlib
import os
import uuid
from typing import Any, Dict, Optional
import structlog
from fastapi import Response
from .base import TelephonyProvider

logger = structlog.get_logger(__name__)


class ExotelTelephonyProvider(TelephonyProvider):
    """
    Exotel implementation of the TelephonyProvider interface.
    
    Env vars required:
      EXOTEL_API_KEY
      EXOTEL_API_TOKEN
      EXOTEL_SID
      EXOTEL_VIRTUAL_NUMBER
      BACKEND_URL  (public URL for WebSocket bridge)
    """
    
    def __init__(self):
        self.api_key = os.getenv("EXOTEL_API_KEY", "")
        self.api_token = os.getenv("EXOTEL_API_TOKEN", "")
        self.sid = os.getenv("EXOTEL_SID", "")
        self.virtual_number = os.getenv("EXOTEL_VIRTUAL_NUMBER", "")
        self.backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        
        if not self.api_key and os.getenv("ENVIRONMENT", "development") == "production":
            raise ValueError("EXOTEL_API_KEY is required in production. Set it in .env.")
    
    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """
        Verify Exotel webhook HMAC-SHA256 signature.
        Exotel signs the raw POST body with EXOTEL_API_TOKEN.
        """
        if not self.api_token:
            if os.getenv("ENVIRONMENT", "development") == "production":
                logger.error("exotel_webhook_token_missing")
                return False
            logger.warning("exotel_webhook_validation_skipped", env="development")
            return True
        
        expected = hmac.new(
            self.api_token.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    
    def handle_incoming(self, request_data: Dict[str, Any]) -> Any:
        """
        Handle an Exotel inbound call webhook.
        
        Exotel sends call data as form POST. We:
        1. Extract caller info
        2. Create a LiveKit room
        3. Spawn the ZylinAgent
        4. Return ExoML (Exotel XML) to connect the caller
        
        Returns a FastAPI Response with ExoML.
        """
        call_sid = request_data.get("CallSid", request_data.get("callsid", ""))
        caller = request_data.get("From", request_data.get("CallFrom", ""))
        called = request_data.get("To", request_data.get("CallTo", self.virtual_number))
        
        call_id = f"exotel-{call_sid[:16]}" if call_sid else f"exotel-{uuid.uuid4().hex[:12]}"
        room_name = f"call-{uuid.uuid4().hex[:12]}"
        
        logger.info(
            "exotel_inbound_call",
            call_sid=call_sid,
            caller=caller,
            called=called,
            call_id=call_id,
            room_name=room_name,
        )
        
        # Spawn agent task
        try:
            asyncio.create_task(
                self._spawn_agent(call_id=call_id, room_name=room_name, caller=caller)
            )
        except RuntimeError:
            # No running event loop in sync context (tests) — skip
            pass
        
        # Exotel WebSocket stream URL
        ws_url = self.backend_url.replace("https://", "wss://").replace("http://", "ws://")
        stream_url = f"{ws_url}/telephony/stream/{call_id}"
        
        # ExoML response — connect caller audio to our WebSocket bridge
        exoml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://zylin.in/audio/greeting.wav</Play>
  <Connect action="{self.backend_url}/telephony/status" method="POST">
    <Stream url="{stream_url}">
      <Parameter name="call_id" value="{call_id}" />
      <Parameter name="room_name" value="{room_name}" />
    </Stream>
  </Connect>
</Response>"""
        
        return Response(content=exoml, media_type="application/xml")
    
    async def _spawn_agent(self, call_id: str, room_name: str, caller: str):
        """Spawn the ZylinAgent for this call."""
        try:
            import sys
            agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent")
            if agent_path not in sys.path:
                sys.path.insert(0, agent_path)
            from agent import ZylinAgent
            agent = ZylinAgent(
                call_id=call_id,
                room_name=room_name,
                languages=["ta", "en"],
            )
            await agent.start()
        except Exception as exc:
            logger.error("exotel_agent_spawn_failed", call_id=call_id, error=str(exc))
    
    def transfer_call(self, call_sid: str, target_number: str) -> Any:
        """
        Transfer an active Exotel call to a human agent number.
        Uses Exotel Calls API.
        """
        import urllib.request
        import urllib.parse
        import json
        
        if not self.api_key:
            logger.warning("exotel_transfer_skipped_no_credentials")
            return {"error": "Exotel credentials not configured"}
        
        url = f"https://api.exotel.com/v1/Accounts/{self.sid}/Calls/{call_sid}.json"
        data = urllib.parse.urlencode({
            "Url": f"http://my.exotel.com/{self.sid}/exoml/start/{target_number}",
            "Method": "POST",
        }).encode()
        
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Authorization": f"Basic {self.api_key}:{self.api_token}"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            logger.error("exotel_transfer_failed", error=str(exc))
            return {"error": str(exc)}
    
    def end_call(self, call_sid: str) -> Any:
        """End an Exotel call via API."""
        logger.info("exotel_end_call", call_sid=call_sid)
        # In production: POST to Exotel Calls API to terminate call
        return {"status": "end_call_requested", "call_sid": call_sid}
