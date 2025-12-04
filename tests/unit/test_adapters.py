"""
Unit Tests for Zylin Adapters
Tests for LiveKit, STT, LLM, and TTS adapters using mocks.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))


class TestMockLiveKitClient:
    """Test MockLiveKitClient functionality"""
    
    @pytest.mark.asyncio
    async def test_create_room(self):
        from adapters.livekit_client import MockLiveKitClient
        
        client = MockLiveKitClient("test-call-1")
        room_info = await client.create_room("test-room")
        
        assert room_info["name"] == "test-room"
        assert "mock-room" in room_info["sid"]
    
    @pytest.mark.asyncio
    async def test_join_room(self):
        from adapters.livekit_client import MockLiveKitClient
        
        client = MockLiveKitClient("test-call-2")
        await client.join_room_as_agent("test-room", "agent-123")
        
        assert client.connected is True
        assert client.room_name == "test-room"
    
    @pytest.mark.asyncio
    async def test_publish_audio(self):
        from adapters.livekit_client import MockLiveKitClient
        
        client = MockLiveKitClient("test-call-3")
        await client.join_room_as_agent("test-room")
        
        audio_data = b'\x00' * 1000
        await client.publish_audio_chunk(audio_data, sample_rate=16000)
        
        published = client.get_published_audio()
        assert len(published) == 1
        assert published[0]["data"] == audio_data
        assert published[0]["sample_rate"] == 16000
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        from adapters.livekit_client import MockLiveKitClient
        
        client = MockLiveKitClient("test-call-4")
        await client.join_room_as_agent("test-room")
        assert client.connected is True
        
        await client.disconnect()
        assert client.connected is False


class TestMockSTTAdapter:
    """Test MockSTTAdapter functionality"""
    
    @pytest.mark.asyncio
    async def test_mock_transcripts(self):
        from adapters.stt_adapter import MockSTTAdapter, TranscriptType
        
        mock_transcripts = ["Hello world", "How are you?"]
        adapter = MockSTTAdapter("test-call", mock_transcripts=mock_transcripts)
        
        # Send audio to trigger transcription
        audio_data = b'\x00' * 32000
        await adapter.send_audio_chunk(audio_data)
        
        # Get transcripts
        transcripts = []
        async for transcript in adapter.get_transcript_stream():
            transcripts.append(transcript)
            if transcript.is_final:
                break
        
        # Should have partial and final
        assert len(transcripts) >= 2
        assert any(not t.is_final for t in transcripts)  # Has partial
        assert any(t.is_final for t in transcripts)      # Has final
        
        final_transcript = [t for t in transcripts if t.is_final][0]
        assert final_transcript.text in mock_transcripts
    
    @pytest.mark.asyncio
    async def test_reset(self):
        from adapters.stt_adapter import MockSTTAdapter
        
        adapter = MockSTTAdapter("test-call")
        adapter.audio_buffer_size = 10000
        
        await adapter.reset()
        assert adapter.audio_buffer_size == 0


class TestMockLLMAdapter:
    """Test MockLLMAdapter functionality"""
    
    @pytest.mark.asyncio
    async def test_generate_default(self):
        from adapters.llm_adapter import MockLLMAdapter
        
        adapter = MockLLMAdapter("test-call")
        response = await adapter.generate("Test prompt")
        
        assert response is not None
        assert "You said:" in response or "Test prompt" in response
    
    @pytest.mark.asyncio
    async def test_generate_custom_response(self):
        from adapters.llm_adapter import MockLLMAdapter
        
        mock_responses = {
            "hello": "Hi there! How can I help you?",
            "help": "I'm here to assist you."
        }
        
        adapter = MockLLMAdapter("test-call", mock_responses=mock_responses)
        
        response = await adapter.generate("I need help")
        assert response == "I'm here to assist you."
    
    @pytest.mark.asyncio
    async def test_generate_stream(self):
        from adapters.llm_adapter import MockLLMAdapter
        
        adapter = MockLLMAdapter("test-call")
        
        chunks = []
        async for chunk in adapter.generate_stream("Test prompt"):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert len(full_response) > 0


class TestMockTTSAdapter:
    """Test MockTTSAdapter functionality"""
    
    @pytest.mark.asyncio
    async def test_stream_speech(self):
        from adapters.tts_adapter import MockTTSAdapter
        
        adapter = MockTTSAdapter("test-call", audio_duration_ms=1000)
        
        chunks = []
        async for chunk in adapter.stream_speech("Hello world"):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        
        # Verify audio format (should be bytes)
        for chunk in chunks:
            assert isinstance(chunk, bytes)
    
    @pytest.mark.asyncio
    async def test_close(self):
        from adapters.tts_adapter import MockTTSAdapter
        
        adapter = MockTTSAdapter("test-call")
        await adapter.close()  # Should not raise


class TestLLMAdapter:
    """Test real LLMAdapter with mocked OpenAI"""
    
    @pytest.mark.asyncio
    async def test_generate_with_mock_openai(self):
        from adapters.llm_adapter import LLMAdapter, LLMConfig
        
        config = LLMConfig(api_key="test-key", model="gpt-4")
        
        with patch("adapters.llm_adapter.openai.AsyncOpenAI") as mock_openai:
            # Setup mock
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = Mock()
            mock_response.usage.total_tokens = 50
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            adapter = LLMAdapter("test-call", config)
            response = await adapter.generate("Test prompt")
            
            assert response == "Test response"
            mock_client.chat.completions.create.assert_called_once()


class TestFactoryFunctions:
    """Test factory functions for creating adapters"""
    
    def test_create_livekit_client_mock(self):
        from adapters.livekit_client import create_livekit_client, MockLiveKitClient
        
        client = create_livekit_client("test-call", use_mock=True)
        assert isinstance(client, MockLiveKitClient)
    
    def test_create_stt_adapter_mock(self):
        from adapters.stt_adapter import create_stt_adapter, MockSTTAdapter
        
        adapter = create_stt_adapter("test-call", provider="mock")
        assert isinstance(adapter, MockSTTAdapter)
    
    def test_create_llm_adapter_mock(self):
        from adapters.llm_adapter import create_llm_adapter, MockLLMAdapter
        
        adapter = create_llm_adapter("test-call", use_mock=True)
        assert isinstance(adapter, MockLLMAdapter)
    
    def test_create_tts_adapter_mock(self):
        from adapters.tts_adapter import create_tts_adapter, MockTTSAdapter
        
        adapter = create_tts_adapter("test-call", use_mock=True)
        assert isinstance(adapter, MockTTSAdapter)


class TestDatabaseModels:
    """Test database models and operations"""
    
    def test_create_call_record(self):
        from models import DatabaseManager, create_call_record
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()
        
        session = db_manager.get_session()
        try:
            call = create_call_record(
                session,
                call_id="test-call-1",
                room_name="test-room",
                agent_identity="agent-1"
            )
            
            assert call.call_id == "test-call-1"
            assert call.room_name == "test-room"
            assert call.status == "active"
        finally:
            session.close()
    
    def test_add_transcript_chunk(self):
        from models import DatabaseManager, create_call_record, add_transcript_chunk
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()
        
        session = db_manager.get_session()
        try:
            create_call_record(session, "test-call", "test-room", "agent-1")
            
            chunk = add_transcript_chunk(
                session,
                call_id="test-call",
                text="Hello world",
                is_final=True,
                confidence=0.95,
                sequence_number=0
            )
            
            assert chunk.text == "Hello world"
            assert chunk.is_final is True
            assert chunk.confidence == 0.95
        finally:
            session.close()
    
    def test_add_agent_reply(self):
        from models import DatabaseManager, create_call_record, add_agent_reply
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()
        
        session = db_manager.get_session()
        try:
            create_call_record(session, "test-call", "test-room", "agent-1")
            
            reply = add_agent_reply(
                session,
                call_id="test-call",
                prompt="Hello",
                response_text="Hi there!",
                sequence_number=0
            )
            
            assert reply.prompt == "Hello"
            assert reply.response_text == "Hi there!"
        finally:
            session.close()
    
    def test_update_call_status(self):
        from models import DatabaseManager, create_call_record, update_call_status
        
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()
        
        session = db_manager.get_session()
        try:
            create_call_record(session, "test-call", "test-room", "agent-1")
            
            updated = update_call_status(session, "test-call", "completed")
            
            assert updated.status == "completed"
            assert updated.end_time is not None
        finally:
            session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
