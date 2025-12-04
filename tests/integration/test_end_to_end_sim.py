"""
Integration Tests for Zylin Voice Agent
End-to-end simulation tests that verify DB persistence and complete flow.
"""
import pytest
import asyncio
import sys
import os
import uuid

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))


@pytest.mark.asyncio
async def test_end_to_end_simulation():
    """
    End-to-end simulation test.
    
    Verifies:
    1. Call record is created
    2. Transcripts are saved to database
    3. Agent replies are generated and saved
    4. Call status is updated to completed
    """
    from adapters.livekit_client import MockLiveKitClient
    from adapters.stt_adapter import MockSTTAdapter
    from adapters.llm_adapter import MockLLMAdapter
    from adapters.tts_adapter import MockTTSAdapter
    from models import (
        DatabaseManager,
        create_call_record,
        add_transcript_chunk,
        add_agent_reply,
        update_call_status,
        get_call_record,
        get_call_transcripts,
        get_call_replies
    )
    
    # Setup
    call_id = f"integration-test-{uuid.uuid4().hex[:8]}"
    room_name = "test-room"
    
    mock_transcripts = [
        "Hello, I need assistance.",
        "Can you help me with my order?",
        "Thank you for your help."
    ]
    
    # Initialize components
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.create_tables()
    
    livekit = MockLiveKitClient(call_id)
    stt = MockSTTAdapter(call_id, mock_transcripts=mock_transcripts)
    llm = MockLLMAdapter(call_id)
    tts = MockTTSAdapter(call_id)
    
    # Simulate complete flow
    try:
        # 1. Join room
        await livekit.join_room_as_agent(room_name, f"zylin-agent-{call_id}")
        assert livekit.connected is True
        
        # 2. Create call record
        session = db_manager.get_session()
        try:
            call = create_call_record(
                session,
                call_id=call_id,
                room_name=room_name,
                agent_identity=f"zylin-agent-{call_id}"
            )
            assert call.call_id == call_id
            assert call.status == "active"
        finally:
            session.close()
        
        # 3. Process transcripts and generate responses
        sequence = 0
        
        for transcript_text in mock_transcripts:
            # Simulate audio input
            fake_audio = b'\x00' * 32000  # 2 seconds of silence
            await stt.send_audio_chunk(fake_audio)
            
            # Get transcript
            got_final = False
            async for transcript in stt.get_transcript_stream():
                if transcript.is_final:
                    got_final = True
                    
                    # Save transcript to DB
                    session = db_manager.get_session()
                    try:
                        chunk = add_transcript_chunk(
                            session,
                            call_id=call_id,
                            text=transcript.text,
                            is_final=True,
                            confidence=transcript.confidence,
                            sequence_number=sequence,
                            speaker="caller"
                        )
                        assert chunk.text == transcript.text
                        sequence += 1
                    finally:
                        session.close()
                    
                    # Generate LLM response
                    llm_response = await llm.generate(transcript.text)
                    assert llm_response is not None
                    assert len(llm_response) > 0
                    
                    # Save agent reply to DB
                    session = db_manager.get_session()
                    try:
                        reply = add_agent_reply(
                            session,
                            call_id=call_id,
                            prompt=transcript.text,
                            response_text=llm_response,
                            sequence_number=sequence
                        )
                        assert reply.response_text == llm_response
                        sequence += 1
                    finally:
                        session.close()
                    
                    # Generate and publish TTS
                    tts_chunks = 0
                    async for audio_chunk in tts.stream_speech(llm_response):
                        await livekit.publish_audio_chunk(audio_chunk)
                        tts_chunks += 1
                    
                    assert tts_chunks > 0
                    break
            
            assert got_final, f"Did not get final transcript for: {transcript_text}"
        
        # 4. Mark call as completed
        session = db_manager.get_session()
        try:
            updated_call = update_call_status(session, call_id, "completed")
            assert updated_call.status == "completed"
            assert updated_call.end_time is not None
        finally:
            session.close()
        
        # 5. Verify database records
        session = db_manager.get_session()
        try:
            # Check call record
            call = get_call_record(session, call_id)
            assert call is not None
            assert call.status == "completed"
            
            # Check transcripts
            transcripts = get_call_transcripts(session, call_id, final_only=True)
            assert len(transcripts) == len(mock_transcripts), \
                f"Expected {len(mock_transcripts)} transcripts, got {len(transcripts)}"
            
            for i, transcript in enumerate(transcripts):
                assert transcript.text in mock_transcripts
                assert transcript.is_final is True
                assert transcript.call_id == call_id
            
            # Check agent replies
            replies = get_call_replies(session, call_id)
            assert len(replies) == len(mock_transcripts), \
                f"Expected {len(mock_transcripts)} replies, got {len(replies)}"
            
            for reply in replies:
                assert reply.response_text is not None
                assert len(reply.response_text) > 0
                assert reply.call_id == call_id
            
            # Check published audio
            published_audio = livekit.get_published_audio()
            assert len(published_audio) > 0, "No audio was published"
            
        finally:
            session.close()
        
        # Success!
        print(f"\n✅ Integration test passed!")
        print(f"   - Call ID: {call_id}")
        print(f"   - Transcripts saved: {len(mock_transcripts)}")
        print(f"   - Agent replies saved: {len(mock_transcripts)}")
        print(f"   - Audio chunks published: {len(published_audio)}")
        
    finally:
        # Cleanup
        await stt.close()
        await tts.close()
        await livekit.disconnect()


@pytest.mark.asyncio
async def test_multiple_calls_isolation():
    """
    Test that multiple calls are properly isolated in the database.
    """
    from models import DatabaseManager, create_call_record, get_call_record
    
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.create_tables()
    
    # Create multiple call records
    call_ids = [f"test-call-{i}" for i in range(3)]
    
    session = db_manager.get_session()
    try:
        for call_id in call_ids:
            create_call_record(
                session,
                call_id=call_id,
                room_name=f"room-{call_id}",
                agent_identity=f"agent-{call_id}"
            )
        
        # Verify each call is distinct
        for call_id in call_ids:
            call = get_call_record(session, call_id)
            assert call is not None
            assert call.call_id == call_id
            assert call.room_name == f"room-{call_id}"
    
    finally:
        session.close()


@pytest.mark.asyncio
async def test_error_handling():
    """
    Test error handling and status updates.
    """
    from models import DatabaseManager, create_call_record, update_call_status, get_call_record
    
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.create_tables()
    
    call_id = "error-test-call"
    
    session = db_manager.get_session()
    try:
        # Create call
        create_call_record(session, call_id, "test-room", "agent-1")
        
        # Simulate error
        error_msg = "Test error occurred"
        update_call_status(session, call_id, "failed", error_message=error_msg)
        
        # Verify error is recorded
        call = get_call_record(session, call_id)
        assert call.status == "failed"
        assert call.error_message == error_msg
        assert call.end_time is not None
    
    finally:
        session.close()


@pytest.mark.asyncio
async def test_transcript_sequence():
    """
    Test that transcripts maintain proper sequence numbering.
    """
    from models import DatabaseManager, create_call_record, add_transcript_chunk, get_call_transcripts
    
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.create_tables()
    
    call_id = "sequence-test-call"
    
    session = db_manager.get_session()
    try:
        create_call_record(session, call_id, "test-room", "agent-1")
        
        # Add transcripts in sequence
        texts = ["First", "Second", "Third", "Fourth", "Fifth"]
        for i, text in enumerate(texts):
            add_transcript_chunk(
                session,
                call_id=call_id,
                text=text,
                is_final=True,
                confidence=0.9,
                sequence_number=i
            )
        
        # Verify sequence
        transcripts = get_call_transcripts(session, call_id)
        assert len(transcripts) == len(texts)
        
        for i, transcript in enumerate(transcripts):
            assert transcript.sequence_number == i
            assert transcript.text == texts[i]
    
    finally:
        session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
