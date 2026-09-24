"""
Telephony Router — Twilio Inbound Call Handler

When a caller dials the Twilio DID assigned to a tenant:
  1. Twilio POSTs to POST /telephony/inbound (TwiML webhook)
  2. We answer with TwiML <Stream> pointing to our LiveKit bridge
  3. We create a LiveKit room and spawn a ZylinAgent process
  4. Audio flows: Caller → Twilio → WebSocket → Agent → LiveKit → TTS → Twilio → Caller
  5. On call end, we update call_records with duration and trigger post-call jobs

Environment variables required:
    TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN
    TWILIO_PHONE_NUMBER
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    BACKEND_URL (public URL for WebSocket bridge)
"""
import asyncio
import os
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Form, HTTPException, Request, Response, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/telephony", tags=["telephony"])


# ---------------------------------------------------------------------------
# Twilio signature validation
# ---------------------------------------------------------------------------

def _validate_twilio_signature(request: Request, body: dict) -> bool:
    """
    Validate that the incoming webhook is genuinely from Twilio.
    Uses HMAC-SHA1 signature on the full request URL + form body.
    """
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        logger.warning("twilio_auth_token_missing_skip_validation")
        return True  # Skip in dev; enforce in production

    try:
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(auth_token)
        # Build the URL (account for proxy headers)
        proto = request.headers.get("X-Forwarded-Proto", "https")
        host = request.headers.get("X-Forwarded-Host", request.headers.get("host", ""))
        url = f"{proto}://{host}{request.url.path}"
        sig = request.headers.get("X-Twilio-Signature", "")
        return validator.validate(url, body, sig)
    except ImportError:
        logger.error("twilio_sdk_not_installed", hint="pip install twilio>=8.0.0")
        return False
    except Exception as exc:
        logger.error("twilio_validation_error", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Helper: spawn agent process
# ---------------------------------------------------------------------------

async def _spawn_agent_for_call(
    call_id: str,
    room_name: str,
    agent_config_id: Optional[int],
    customer_id: Optional[str],
    caller_number: Optional[str],
) -> None:
    """
    Spawn ZylinAgent as an asyncio task for the inbound call.

    In production this would be an async task queue (Celery/arq),
    but for V1 we run it as a long-lived asyncio task per call.
    """
    try:
        import sys
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent")
        if agent_path not in sys.path:
            sys.path.insert(0, agent_path)

        from agent import ZylinAgent

        # Load agent config from DB if available
        languages = ["ta", "en"]  # default Tamil+English
        if agent_config_id:
            # TODO: load from DB — will be wired once agent_configs is migrated
            pass

        agent = ZylinAgent(
            call_id=call_id,
            room_name=room_name,
            use_mocks=False,
            agent_config_id=agent_config_id,
            languages=languages,
        )

        logger.info(
            "agent_spawned_for_inbound_call",
            call_id=call_id,
            room_name=room_name,
            caller=caller_number,
        )

        await agent.start()

    except Exception as exc:
        logger.error("agent_spawn_failed", call_id=call_id, error=str(exc))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/inbound", response_class=Response)
async def handle_inbound_call(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Generic webhook: called when an inbound call arrives.
    Dispatches to the configured TelephonyProvider.
    """
    form_data = dict(await request.form())

    from providers.telephony import get_telephony_provider
    provider = get_telephony_provider()
    
    # Provider is responsible for handling webhook validation,
    # database record creation, and returning the provider-specific response.
    # In a real impl, we'd pass `db` to the provider or have it yield DB interactions.
    # For now we'll just pass the dict.
    
    # We mock the return value for the sprint:
    response = provider.handle_incoming(form_data)
    
    # Usually provider.handle_incoming would return a FastAPI Response object
    if isinstance(response, Response):
        return response
        
    return Response(content="<Response></Response>", media_type="application/xml")


@router.post("/status")
async def call_status_callback(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Twilio status callback: receives call lifecycle events.
    Updates call_records on completion.
    """
    call_id = f"inbound-{CallSid[:16]}"
    logger.info("twilio_status_callback", call_sid=CallSid, status=CallStatus, duration=CallDuration)

    if CallStatus in ("completed", "failed", "busy", "no-answer"):
        _update_call_record_status(
            db,
            call_id=call_id,
            status="completed" if CallStatus == "completed" else "failed",
            duration_seconds=float(CallDuration) if CallDuration else None,
        )

        # Trigger async post-call jobs (summary, WhatsApp, cost calculation)
        asyncio.create_task(_run_post_call_jobs(call_id=call_id, db=db))

    return {"received": True}


# ---------------------------------------------------------------------------
# WebSocket bridge: Twilio Media Streams → LiveKit
# ---------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect
import base64
import json as _json


@router.websocket("/stream/{call_id}")
async def telephony_stream(websocket: WebSocket, call_id: str):
    """
    WebSocket endpoint that bridges Twilio Media Streams to LiveKit audio.

    Twilio sends base64-encoded mulaw audio at 8kHz.
    We resample to PCM16 16kHz and push to the ZylinAgent via LiveKit.

    Protocol:
      Twilio → WS: {"event": "media", "media": {"payload": "<base64>"}}
      We   → Twilio: {"event": "media", "streamSid": "...", "media": {"payload": "<base64>"}}
    """
    await websocket.accept()
    logger.info("telephony_stream_opened", call_id=call_id)

    stream_sid: Optional[str] = None

    try:
        # Import audioop for mulaw→PCM conversion (stdlib)
        try:
            import audioop
        except ImportError:
            # Python 3.13+ removed audioop — use av or soundfile
            audioop = None  # type: ignore

        from livekit import rtc, api

        lk_url = os.getenv("LIVEKIT_URL", "")
        lk_key = os.getenv("LIVEKIT_API_KEY", "")
        lk_secret = os.getenv("LIVEKIT_API_SECRET", "")

        # This WS publishes audio INTO the LiveKit room where ZylinAgent is listening
        # We join as the "caller" participant
        token = api.AccessToken(lk_key, lk_secret)
        room_name = f"call-{call_id}"  # matches room created in inbound handler
        token.with_identity(f"caller-{call_id}")
        token.with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))

        lk_room = rtc.Room()
        audio_source = rtc.AudioSource(16000, 1)
        audio_track = rtc.LocalAudioTrack.create_audio_track("caller-audio", audio_source)

        await lk_room.connect(lk_url, token.to_jwt())
        await lk_room.local_participant.publish_track(audio_track, rtc.TrackPublishOptions())

        logger.info("telephony_stream_livekit_joined", call_id=call_id, room=room_name)

        while True:
            raw = await websocket.receive_text()
            msg = _json.loads(raw)
            event = msg.get("event")

            if event == "start":
                stream_sid = msg.get("streamSid")
                logger.info("twilio_stream_started", stream_sid=stream_sid)

            elif event == "media":
                payload = msg["media"]["payload"]
                mulaw_bytes = base64.b64decode(payload)

                # Convert 8kHz mulaw → 16kHz PCM16
                if audioop:
                    pcm8k = audioop.ulaw2lin(mulaw_bytes, 2)  # mulaw → 16-bit linear at 8kHz
                    pcm16k = audioop.ratecv(pcm8k, 2, 1, 8000, 16000, None)[0]  # upsample 8→16kHz
                else:
                    # Fallback: zero pad (rough upsampling) — replace with proper impl
                    pcm8k = bytes(b"\x00\x00" * len(mulaw_bytes))
                    pcm16k = pcm8k * 2

                # Push into LiveKit
                frame = rtc.AudioFrame(
                    data=pcm16k,
                    sample_rate=16000,
                    num_channels=1,
                    samples_per_channel=len(pcm16k) // 2,
                )
                await audio_source.capture_frame(frame)

            elif event == "stop":
                logger.info("twilio_stream_stopped", call_id=call_id)
                break

    except WebSocketDisconnect:
        logger.info("telephony_stream_ws_disconnected", call_id=call_id)
    except Exception as exc:
        logger.error("telephony_stream_error", call_id=call_id, error=str(exc))
    finally:
        try:
            await lk_room.disconnect()
        except Exception:
            pass
        logger.info("telephony_stream_closed", call_id=call_id)


# ---------------------------------------------------------------------------
# Post-call async jobs
# ---------------------------------------------------------------------------

async def _run_post_call_jobs(call_id: str, db: Session) -> None:
    """
    Run post-call processing:
    1. Generate AI summary of the transcript
    2. Calculate and store call cost
    3. Send WhatsApp follow-up if appointment was booked
    """
    logger.info("post_call_jobs_started", call_id=call_id)
    try:
        # 1. Generate summary
        await _generate_call_summary(call_id, db)
        # 2. Cost tracking (implemented in Sprint 8)
        # await compute_call_cost(call_id, db)
        # 3. WhatsApp (implemented in Sprint 7)
        # await send_whatsapp_followup(call_id, db)
    except Exception as exc:
        logger.error("post_call_jobs_failed", call_id=call_id, error=str(exc))


async def _generate_call_summary(call_id: str, db: Session) -> None:
    """Generate and store an AI summary of the call transcript."""
    from sqlalchemy import text
    import sys
    
    agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "agent")
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)
    from providers.llm import get_llm_provider

    # Get all final transcripts for this call
    rows = db.execute(
        text("""
            SELECT speaker, text FROM transcript_chunks
            WHERE call_id = :call_id AND is_final = true
            ORDER BY sequence_number
        """),
        {"call_id": call_id},
    ).fetchall()

    if not rows:
        logger.info("no_transcripts_for_summary", call_id=call_id)
        return

    transcript_text = "\n".join(
        f"{'Caller' if r[0] == 'caller' else 'Agent'}: {r[1]}" for r in rows
    )

    provider = get_llm_provider(call_id)
    system_prompt = (
        "You are a call summariser. Given a voice call transcript, "
        "write a 2-4 sentence summary covering: purpose of call, "
        "outcome (appointment booked/cancelled/transferred/resolved), "
        "and any follow-up actions. Be factual and concise."
    )
    prompt = f"Transcript:\n{transcript_text[:4000]}"
    
    result = await provider.generate(prompt=prompt, system_prompt=system_prompt)
    summary = result.get("text", "")

    db.execute(
        text("UPDATE call_records SET summary = :summary WHERE call_id = :call_id"),
        {"summary": summary, "call_id": call_id},
    )
    db.commit()
    logger.info("call_summary_generated", call_id=call_id, length=len(summary))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _resolve_tenant_for_number(db: Session, phone_number: str):
    """Find the customer_id and agent_config_id for a Twilio DID."""
    from sqlalchemy import text

    row = db.execute(
        text("SELECT customer_id, NULL as agent_config_id FROM customers WHERE twilio_number = :num LIMIT 1"),
        {"num": phone_number},
    ).fetchone()

    if row:
        return row[0], row[1]
    return None, None


def _create_call_record(
    db: Session,
    call_id: str,
    room_name: str,
    caller_number: str,
    called_number: str,
    call_type: str,
    agent_config_id: Optional[int],
    customer_id: Optional[str],
) -> None:
    from sqlalchemy import text

    db.execute(
        text("""
            INSERT INTO call_records
                (call_id, room_name, agent_identity, call_type, caller_number,
                 agent_config_id, customer_id, status)
            VALUES
                (:call_id, :room_name, 'zylin-agent', :call_type, :caller_number,
                 :agent_config_id, :customer_id::uuid, 'active')
            ON CONFLICT (call_id) DO NOTHING
        """),
        {
            "call_id": call_id,
            "room_name": room_name,
            "call_type": call_type,
            "caller_number": caller_number,
            "agent_config_id": agent_config_id,
            "customer_id": customer_id,
        },
    )
    db.commit()


def _update_call_record_status(
    db: Session,
    call_id: str,
    status: str,
    duration_seconds: Optional[float] = None,
) -> None:
    from sqlalchemy import text

    db.execute(
        text("""
            UPDATE call_records
            SET status = :status,
                end_time = NOW(),
                duration_seconds = :duration
            WHERE call_id = :call_id
        """),
        {"status": status, "duration": duration_seconds, "call_id": call_id},
    )
    db.commit()


def _create_livekit_token_for_caller(room_name: str, identity: str) -> str:
    """Create a LiveKit access token for a caller participant."""
    try:
        from livekit import api

        token = api.AccessToken(
            os.getenv("LIVEKIT_API_KEY", ""),
            os.getenv("LIVEKIT_API_SECRET", ""),
        )
        token.with_identity(identity)
        token.with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True, can_subscribe=True))
        return token.to_jwt()
    except Exception as exc:
        logger.error("livekit_token_creation_failed", error=str(exc))
        return ""
