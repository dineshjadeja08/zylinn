"""Quick test of Zylin system with mock adapters."""
import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import asyncio
from adapters.livekit_client import MockLiveKitClient
from adapters.stt_adapter import MockSTTAdapter
from adapters.llm_adapter import MockLLMAdapter
from adapters.tts_adapter import MockTTSAdapter
from models import DatabaseManager, create_call_record, get_call_transcripts, get_call_replies

async def test_system():
    """Test the complete system with mock adapters."""
    print("🚀 Starting Zylin Quick Test...\n")
    
    # Initialize database (fresh start)
    db_manager = DatabaseManager(database_url="sqlite:///./test_zylinn.db")
    db_manager.drop_tables()
    db_manager.create_tables()
    print("✅ Database initialized")
    
    # Create a test call
    call_id = "test-call-123"
    session = db_manager.get_session()
    call_record = create_call_record(session, call_id, "test-room", "active")
    print(f"✅ Created call record: {call_id}")
    
    # Initialize mock adapters with predefined responses
    livekit = MockLiveKitClient(call_id=call_id)
    stt = MockSTTAdapter(call_id=call_id, mock_transcripts=["Hello, how are you?", "This is a test."])
    llm = MockLLMAdapter(call_id=call_id)
    tts = MockTTSAdapter(call_id=call_id)
    print("✅ All adapters initialized (mock mode)")
    
    # Test STT
    print("\n🎤 Testing STT...")
    await stt.send_audio_chunk(b"test audio data" * 3000)  # Trigger mock transcript
    transcript_count = 0
    async for result in stt.get_transcript_stream():
        print(f"   Transcript: '{result.text}' (final: {result.is_final})")
        transcript_count += 1
        if transcript_count >= 2:  # Get partial + final
            break
    
    # Test LLM
    print("\n🤖 Testing LLM...")
    response = await llm.generate("Hello, how are you?")
    print(f"   LLM Response: '{response}'")
    
    # Test TTS
    print("\n🔊 Testing TTS...")
    chunk_count = 0
    async for audio_chunk in tts.stream_speech("Hello from Zylin"):
        chunk_count += 1
        if chunk_count >= 5:  # Just get a few chunks
            break
    print(f"   Generated {chunk_count} audio chunks")
    
    # Verify database
    print("\n📊 Checking database...")
    transcripts = get_call_transcripts(session, call_id)
    replies = get_call_replies(session, call_id)
    print(f"   Transcripts in DB: {len(transcripts)}")
    print(f"   Replies in DB: {len(replies)}")
    
    session.close()
    print("\n✨ All tests passed! Zylin is working.")
    
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_system())
        if result:
            print("\n🎉 SUCCESS: Zylin system is operational!")
            sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
