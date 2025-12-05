"""
Persistent Zylin Agent Runner
Keeps the agent running and restarts it if needed
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from agent.adapters.livekit_client import create_livekit_client
from agent.adapters.stt_adapter import create_stt_adapter
from agent.adapters.llm_adapter import create_llm_adapter
from agent.adapters.tts_adapter import create_tts_adapter
from backend.models import DatabaseManager, create_call_record
import structlog
import uuid

logger = structlog.get_logger()

async def run_persistent_agent(room_name: str):
    """Run agent that stays alive waiting for callers"""
    load_dotenv()
    
    call_id = f"persistent-{uuid.uuid4().hex[:8]}"
    
    logger.info("starting_persistent_agent", call_id=call_id, room_name=room_name)
    
    # Initialize components
    db_manager = DatabaseManager()
    db_manager.create_tables()
    
    livekit_client = create_livekit_client(call_id, use_mock=False)
    stt_adapter = create_stt_adapter(call_id, use_mock=False)
    llm_adapter = create_llm_adapter(call_id, use_mock=False)
    tts_adapter = create_tts_adapter(call_id, use_mock=False)
    
    # Create call record
    session = db_manager.get_session()
    try:
        create_call_record(session, call_id, room_name, f"zylin-agent-{call_id}")
        logger.info("call_record_created")
    finally:
        session.close()
    
    # Join room
    logger.info("joining_room", room_name=room_name)
    await livekit_client.join_room_as_agent(
        room_name,
        f"zylin-agent-{call_id}"
    )
    logger.info("agent_joined_room", room_name=room_name)
    
    # Keep agent alive
    try:
        while True:
            await asyncio.sleep(10)
            logger.info("agent_heartbeat", room_name=room_name)
    except KeyboardInterrupt:
        logger.info("agent_stopped_by_user")
    finally:
        await livekit_client.disconnect()
        await stt_adapter.close()
        await tts_adapter.close()
        logger.info("agent_cleanup_complete")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Zylin Persistent Agent")
    parser.add_argument("--room", type=str, required=True, help="LiveKit room name")
    args = parser.parse_args()
    
    try:
        asyncio.run(run_persistent_agent(args.room))
    except KeyboardInterrupt:
        print("\n👋 Agent stopped")
