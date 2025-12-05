"""
Zylin AI Voice Agent - Core Agent Logic
Orchestrates the audio loop: LiveKit -> STT -> LLM -> TTS -> LiveKit
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime
from typing import Optional
import structlog
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.livekit_client import create_livekit_client
from adapters.stt_adapter import create_stt_adapter, TranscriptType
from adapters.llm_adapter import create_llm_adapter, get_system_prompt, BOOKING_TOOL
from adapters.tts_adapter import create_tts_adapter

# Import database models
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from models import (
    DatabaseManager,
    create_call_record,
    update_call_status,
    add_transcript_chunk,
    add_agent_reply,
    create_appointment_record
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger(__name__)


class ZylinAgent:
    """
    Main AI voice agent that handles the complete conversation loop.
    
    Flow:
    1. Join LiveKit room
    2. Subscribe to caller audio
    3. Stream audio to STT
    4. On end-of-turn (final transcript), send to LLM
    5. Generate TTS from LLM response
    6. Publish TTS audio back to room
    7. Persist transcripts and replies to database
    """
    
    def __init__(
        self,
        call_id: str,
        room_name: str,
        use_mocks: bool = False,
        mock_transcripts: Optional[list] = None
    ):
        self.call_id = call_id
        self.room_name = room_name
        self.use_mocks = use_mocks
        self.logger = logger.bind(call_id=call_id, room_name=room_name)
        
        # Initialize adapters
        self.livekit_client = create_livekit_client(call_id, use_mock=use_mocks)
        self.stt_adapter = create_stt_adapter(
            call_id,
            mock_transcripts=mock_transcripts if use_mocks else None
        )
        self.llm_adapter = create_llm_adapter(call_id, use_mock=use_mocks)
        self.tts_adapter = create_tts_adapter(call_id, use_mock=use_mocks)
        
        # Initialize database
        self.db_manager = DatabaseManager()
        self.db_manager.create_tables()
        
        # State tracking
        self.transcript_sequence = 0
        self.reply_sequence = 0
        self.current_transcript_buffer = []
        self.is_running = False
        self.agent_identity = f"zylin-agent-{call_id}"
        self.conversation_history = []  # Track conversation for context
        
        # VAD configuration
        self.vad_silence_threshold_ms = int(
            os.getenv("VAD_SILENCE_THRESHOLD_MS", "1500")
        )
        self.last_transcript_time = None
        
        self.logger.info(
            "agent_initialized",
            use_mocks=use_mocks,
            vad_threshold_ms=self.vad_silence_threshold_ms
        )
    
    async def start(self):
        """Start the agent and begin processing"""
        try:
            self.is_running = True
            
            # Create database record
            session = self.db_manager.get_session()
            try:
                create_call_record(
                    session,
                    call_id=self.call_id,
                    room_name=self.room_name,
                    agent_identity=self.agent_identity
                )
                self.logger.info("call_record_created")
            finally:
                session.close()
            
            # Join LiveKit room
            self.logger.info("joining_room", room_name=self.room_name)
            await self.livekit_client.join_room_as_agent(
                self.room_name,
                self.agent_identity
            )
            
            # Start concurrent tasks
            await asyncio.gather(
                self._audio_input_loop(),
                self._transcript_processing_loop(),
                return_exceptions=True
            )
            
        except Exception as e:
            self.logger.error("agent_start_failed", error=str(e))
            
            # Update database with error
            session = self.db_manager.get_session()
            try:
                update_call_status(session, self.call_id, "failed", str(e))
            finally:
                session.close()
            
            raise
        finally:
            await self.cleanup()
    
    async def _audio_input_loop(self):
        """
        Subscribe to audio from LiveKit and stream to STT.
        """
        try:
            self.logger.info("starting_audio_input_loop")
            
            async def on_audio_frame(frame):
                """Handle incoming audio frame"""
                try:
                    # Extract audio data (implementation depends on LiveKit frame format)
                    audio_data = getattr(frame, 'data', b'')
                    if audio_data:
                        await self.stt_adapter.send_audio_chunk(audio_data)
                except Exception as e:
                    self.logger.error("audio_frame_processing_error", error=str(e))
            
            # Subscribe to audio (this will call on_audio_frame for each frame)
            async for frame in self.livekit_client.subscribe_audio(
                on_audio_frame=on_audio_frame
            ):
                if not self.is_running:
                    break
                
                # Also send directly if not using callback
                if hasattr(frame, 'data'):
                    await self.stt_adapter.send_audio_chunk(frame.data)
            
        except Exception as e:
            self.logger.error("audio_input_loop_error", error=str(e))
            raise
    
    async def _transcript_processing_loop(self):
        """
        Process transcripts from STT and trigger LLM responses.
        """
        try:
            self.logger.info("starting_transcript_processing_loop")
            
            async for transcript in self.stt_adapter.get_transcript_stream():
                if not self.is_running:
                    break
                
                self.logger.info(
                    "transcript_received",
                    text=transcript.text,
                    is_final=transcript.is_final,
                    type=transcript.type.value,
                    confidence=transcript.confidence
                )
                
                # Save to database
                session = self.db_manager.get_session()
                try:
                    add_transcript_chunk(
                        session,
                        call_id=self.call_id,
                        text=transcript.text,
                        is_final=transcript.is_final,
                        confidence=transcript.confidence,
                        sequence_number=self.transcript_sequence,
                        speaker="caller"
                    )
                    self.transcript_sequence += 1
                finally:
                    session.close()
                
                # Handle partial transcripts
                if not transcript.is_final:
                    self.current_transcript_buffer.append(transcript.text)
                    self.last_transcript_time = datetime.now()
                    continue
                
                # Handle final transcripts
                final_text = transcript.text
                self.current_transcript_buffer.clear()
                self.last_transcript_time = datetime.now()
                
                # Check if we should generate a response (end-of-turn detection)
                if await self._is_end_of_turn(final_text):
                    await self._generate_and_respond(final_text)
            
        except Exception as e:
            self.logger.error("transcript_processing_error", error=str(e))
            raise
    
    async def _is_end_of_turn(self, text: str) -> bool:
        """
        Determine if this is the end of the caller's turn.
        
        Simple heuristics:
        - Text ends with punctuation (., ?, !)
        - Text is long enough (> 10 characters)
        - Silence threshold met (checked elsewhere)
        
        Args:
            text: Final transcript text
            
        Returns:
            True if end-of-turn detected
        """
        # Must have some content
        if len(text.strip()) < 10:
            return False
        
        # Check for ending punctuation
        if text.strip()[-1] in ['.', '?', '!']:
            return True
        
        # Check silence duration (if last_transcript_time is old enough)
        if self.last_transcript_time:
            silence_ms = (datetime.now() - self.last_transcript_time).total_seconds() * 1000
            if silence_ms >= self.vad_silence_threshold_ms:
                return True
        
        return False
    
    async def _generate_and_respond(self, user_text: str):
        """
        Generate LLM response with tool support and synthesize speech.
        
        Args:
            user_text: User's transcribed text
        """
        try:
            start_time = datetime.now()
            
            self.logger.info("generating_llm_response", user_text=user_text)
            
            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": user_text})
            
            # Build conversation context (last 10 messages for brevity)
            context_messages = self.conversation_history[-10:]
            conversation_context = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Agent'}: {msg['content']}"
                for msg in context_messages
            ])
            
            # Prepare prompt with conversation history
            prompt = f"Conversation history:\n{conversation_context}\n\nRespond to the user's latest message."
            
            # Get system prompt based on environment setting
            prompt_type = os.getenv("LLM_SYSTEM_PROMPT", "appointment")
            system_prompt = get_system_prompt(prompt_type)
            
            # Generate LLM response with tools
            tools = [BOOKING_TOOL] if prompt_type == "appointment" else None
            
            llm_result = await self.llm_adapter.generate_with_tools(
                prompt=prompt,
                system_prompt=system_prompt,
                tools=tools
            )
            
            generation_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            response_text = llm_result.get("text", "")
            tool_calls = llm_result.get("tool_calls", [])
            
            self.logger.info(
                "llm_response_generated",
                response=response_text,
                tool_calls_count=len(tool_calls),
                generation_time_ms=generation_time_ms
            )
            
            # Add assistant response to conversation history
            self.conversation_history.append({"role": "assistant", "content": response_text})
            
            # Execute tool calls if present
            if tool_calls:
                for tool_call in tool_calls:
                    await self._execute_tool(tool_call, response_text)
            
            # Save to database
            session = self.db_manager.get_session()
            try:
                add_agent_reply(
                    session,
                    call_id=self.call_id,
                    prompt=user_text,
                    response_text=response_text,
                    sequence_number=self.reply_sequence,
                    generation_time_ms=generation_time_ms
                )
                self.reply_sequence += 1
            finally:
                session.close()
            
            # Generate and publish TTS (only if there's text to speak)
            if response_text and response_text.strip():
                await self._synthesize_and_publish(response_text)
            
        except Exception as e:
            self.logger.error("generate_and_respond_error", error=str(e))
            # Don't raise - continue processing
    
    async def _execute_tool(self, tool_call: dict, response_text: str):
        """
        Execute a tool call from the LLM.
        
        Args:
            tool_call: Dictionary with 'name' and 'arguments' keys
            response_text: The accompanying response text from the LLM
        """
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})
        
        self.logger.info(
            "executing_tool",
            tool_name=tool_name,
            arguments=arguments
        )
        
        try:
            if tool_name == "book_appointment":
                # Extract appointment details
                customer_name = arguments.get("customer_name")
                appointment_date = arguments.get("appointment_date")
                appointment_time = arguments.get("appointment_time")
                customer_phone = arguments.get("customer_phone")
                customer_email = arguments.get("customer_email")
                service_type = arguments.get("service_type")
                notes = arguments.get("notes")
                
                # Create appointment record in database
                session = self.db_manager.get_session()
                try:
                    appointment = create_appointment_record(
                        session=session,
                        call_id=self.call_id,
                        customer_name=customer_name,
                        appointment_date=appointment_date,
                        appointment_time=appointment_time,
                        customer_phone=customer_phone,
                        customer_email=customer_email,
                        service_type=service_type,
                        notes=notes,
                        status="confirmed"
                    )
                    
                    self.logger.info(
                        "appointment_booked",
                        appointment_id=appointment.id,
                        customer=customer_name,
                        date=appointment_date,
                        time=appointment_time
                    )
                    
                    # Add confirmation to conversation history
                    confirmation = (
                        f"✅ Appointment successfully booked:\n"
                        f"Name: {customer_name}\n"
                        f"Date: {appointment_date}\n"
                        f"Time: {appointment_time}"
                    )
                    if service_type:
                        confirmation += f"\nService: {service_type}"
                    
                    self.conversation_history.append({
                        "role": "system",
                        "content": confirmation
                    })
                    
                finally:
                    session.close()
            else:
                self.logger.warning("unknown_tool", tool_name=tool_name)
                
        except Exception as e:
            self.logger.error(
                "tool_execution_error",
                tool_name=tool_name,
                error=str(e)
            )
    
    async def _synthesize_and_publish(self, text: str):
        """
        Synthesize speech and publish to LiveKit room.
        
        Args:
            text: Text to synthesize
        """
        try:
            self.logger.info("synthesizing_speech", text=text)
            
            audio_chunks_sent = 0
            
            # Stream TTS and publish chunks
            async for audio_chunk in self.tts_adapter.stream_speech(text):
                await self.livekit_client.publish_audio_chunk(audio_chunk)
                audio_chunks_sent += 1
            
            self.logger.info(
                "speech_published",
                chunks_sent=audio_chunks_sent
            )
            
        except Exception as e:
            self.logger.error("synthesize_and_publish_error", error=str(e))
    
    async def cleanup(self):
        """Clean up resources and close connections"""
        self.logger.info("cleaning_up")
        self.is_running = False
        
        try:
            # Close adapters
            await self.stt_adapter.close()
            await self.tts_adapter.close()
            await self.livekit_client.disconnect()
            
            # Update database
            session = self.db_manager.get_session()
            try:
                update_call_status(session, self.call_id, "completed")
            finally:
                session.close()
            
            self.logger.info("cleanup_complete")
            
        except Exception as e:
            self.logger.error("cleanup_error", error=str(e))
    
    async def stop(self):
        """Stop the agent gracefully"""
        self.logger.info("stopping_agent")
        self.is_running = False


async def main():
    """Main entry point for the agent"""
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Zylin AI Voice Agent")
    parser.add_argument("--room", type=str, required=True, help="LiveKit room name")
    parser.add_argument("--call-id", type=str, help="Call ID (auto-generated if not provided)")
    parser.add_argument("--mock", action="store_true", help="Use mock adapters for testing")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # Generate call ID if not provided
    call_id = args.call_id or f"call-{uuid.uuid4().hex[:8]}"
    
    # Configure logging level
    os.environ["LOG_LEVEL"] = args.log_level
    
    logger.info(
        "starting_zylin_agent",
        call_id=call_id,
        room_name=args.room,
        mock_mode=args.mock
    )
    
    # Create and start agent
    agent = ZylinAgent(
        call_id=call_id,
        room_name=args.room,
        use_mocks=args.mock
    )
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("agent_interrupted_by_user")
        await agent.stop()
    except Exception as e:
        logger.error("agent_failed", error=str(e))
        raise
    finally:
        logger.info("agent_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
