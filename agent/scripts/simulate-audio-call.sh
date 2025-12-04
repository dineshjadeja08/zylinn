#!/bin/bash
# Simulate an audio call for testing
set -e

echo "🎙️  Simulating Audio Call..."

# Change to agent directory
cd "$(dirname "$0")/.."

# Load environment variables
if [ -f "../.env" ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Parse arguments
AUDIO_FILE=""
CALL_ID="test-call-$(date +%s)"
ROOM_NAME="test-room"

while [[ $# -gt 0 ]]; do
    case $1 in
        --audio)
            AUDIO_FILE="$2"
            shift 2
            ;;
        --call-id)
            CALL_ID="$2"
            shift 2
            ;;
        --room)
            ROOM_NAME="$2"
            shift 2
            ;;
        *)
            AUDIO_FILE="$1"
            shift
            ;;
    esac
done

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

# Create simulation script
cat > simulate_call.py << 'EOF'
import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from adapters.livekit_client import MockLiveKitClient
from adapters.stt_adapter import MockSTTAdapter
from adapters.llm_adapter import MockLLMAdapter
from adapters.tts_adapter import MockTTSAdapter
from models import DatabaseManager, get_call_record, get_call_transcripts, get_call_replies

async def simulate_call(call_id, room_name, audio_file=None):
    """Simulate a complete call"""
    print(f"📞 Simulating call: {call_id} in room: {room_name}")
    
    # Mock transcripts to simulate
    mock_transcripts = [
        "Hello, can you hear me?",
        "I need help with my account.",
        "My account number is 12345."
    ]
    
    # Initialize database
    db_manager = DatabaseManager()
    db_manager.create_tables()
    
    # Create mock adapters
    livekit = MockLiveKitClient(call_id)
    stt = MockSTTAdapter(call_id, mock_transcripts=mock_transcripts)
    llm = MockLLMAdapter(call_id)
    tts = MockTTSAdapter(call_id)
    
    # Simulate joining room
    await livekit.join_room_as_agent(room_name, f"zylin-agent-{call_id}")
    
    # Simulate call record creation
    from models import create_call_record, add_transcript_chunk, add_agent_reply, update_call_status
    
    session = db_manager.get_session()
    try:
        create_call_record(session, call_id, room_name, f"zylin-agent-{call_id}")
        print("✅ Call record created")
        
        # Simulate processing transcripts
        seq = 0
        for transcript_text in mock_transcripts:
            # Simulate audio processing
            fake_audio = b'\x00' * 16000  # 1 second of silence
            await stt.send_audio_chunk(fake_audio)
            
            # Get transcript
            transcript_stream = stt.get_transcript_stream()
            async for transcript in transcript_stream:
                if transcript.is_final:
                    print(f"📝 Transcript: {transcript.text}")
                    
                    # Save to DB
                    add_transcript_chunk(
                        session, call_id, transcript.text,
                        True, transcript.confidence, seq
                    )
                    seq += 1
                    
                    # Generate LLM response
                    response = await llm.generate(transcript.text)
                    print(f"🤖 Agent response: {response}")
                    
                    # Save reply to DB
                    add_agent_reply(
                        session, call_id, transcript.text,
                        response, seq
                    )
                    seq += 1
                    
                    # Generate TTS
                    audio_chunks = 0
                    async for chunk in tts.stream_speech(response):
                        await livekit.publish_audio_chunk(chunk)
                        audio_chunks += 1
                    
                    print(f"🔊 Published {audio_chunks} audio chunks")
                    break
        
        # Mark call as completed
        update_call_status(session, call_id, "completed")
        print("✅ Call completed")
        
    finally:
        session.close()
    
    # Verify database records
    print("\n🔍 Verifying database records...")
    session = db_manager.get_session()
    try:
        call = get_call_record(session, call_id)
        transcripts = get_call_transcripts(session, call_id, final_only=True)
        replies = get_call_replies(session, call_id)
        
        print(f"  Call status: {call.status}")
        print(f"  Transcripts: {len(transcripts)}")
        print(f"  Agent replies: {len(replies)}")
        
        if len(transcripts) > 0 and len(replies) > 0:
            print("\n✅ SIMULATION PASSED:")
            print(f"   - {len(transcripts)} transcript(s) saved")
            print(f"   - {len(replies)} agent reply/replies saved")
            return True
        else:
            print("\n❌ SIMULATION FAILED: No transcripts or replies found")
            return False
            
    finally:
        session.close()

if __name__ == "__main__":
    call_id = sys.argv[1] if len(sys.argv) > 1 else f"sim-{uuid.uuid4().hex[:8]}"
    room = sys.argv[2] if len(sys.argv) > 2 else "test-room"
    audio = sys.argv[3] if len(sys.argv) > 3 else None
    
    success = asyncio.run(simulate_call(call_id, room, audio))
    sys.exit(0 if success else 1)
EOF

# Run simulation
echo "🚀 Running simulation..."
python simulate_call.py "$CALL_ID" "$ROOM_NAME" "$AUDIO_FILE"

# Cleanup
rm simulate_call.py

echo "✅ Simulation complete!"
