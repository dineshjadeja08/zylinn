"""
LiveKit Client Adapter
Handles connection to LiveKit rooms, audio subscription, and publishing.
"""
import asyncio
import os
from typing import Optional, Callable, AsyncIterator
from dataclasses import dataclass
import structlog
from livekit import rtc, api

logger = structlog.get_logger(__name__)


@dataclass
class LiveKitConfig:
    """Configuration for LiveKit connection"""
    url: str
    api_key: str
    api_secret: str


class LiveKitClient:
    """
    LiveKit client for managing room connections and audio streams.
    
    Handles:
    - Creating and joining rooms
    - Subscribing to participant audio
    - Publishing agent audio
    """
    
    def __init__(self, config: LiveKitConfig, call_id: str):
        self.config = config
        self.call_id = call_id
        self.room: Optional[rtc.Room] = None
        self.audio_source: Optional[rtc.AudioSource] = None
        self.logger = logger.bind(call_id=call_id)
        
    async def create_room(self, room_name: str) -> dict:
        """
        Create a new LiveKit room using the API.
        
        Args:
            room_name: Name of the room to create
            
        Returns:
            Room metadata dictionary
        """
        try:
            lk_api = api.LiveKitAPI(
                self.config.url,
                self.config.api_key,
                self.config.api_secret
            )
            
            room_info = await lk_api.room.create_room(
                api.CreateRoomRequest(name=room_name)
            )
            
            self.logger.info(
                "room_created",
                room_name=room_name,
                room_sid=room_info.sid
            )
            
            return {
                "name": room_info.name,
                "sid": room_info.sid,
                "creation_time": room_info.creation_time
            }
        except Exception as e:
            self.logger.error("room_creation_failed", error=str(e), room_name=room_name)
            raise
    
    async def join_room_as_agent(
        self,
        room_name: str,
        identity: Optional[str] = None
    ) -> rtc.Room:
        """
        Join a LiveKit room as an agent participant.
        
        Args:
            room_name: Name of the room to join
            identity: Agent identity (defaults to zylin-agent-{call_id})
            
        Returns:
            Connected Room object
        """
        if identity is None:
            identity = f"zylin-agent-{self.call_id}"
        
        try:
            # Generate access token
            token = api.AccessToken(
                self.config.api_key,
                self.config.api_secret
            )
            token.with_identity(identity)
            token.with_name("Zylin Agent")
            token.with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
            
            jwt_token = token.to_jwt()
            
            # Connect to room
            self.room = rtc.Room()
            
            # Setup event handlers
            @self.room.on("participant_connected")
            def on_participant_connected(participant: rtc.RemoteParticipant):
                self.logger.info(
                    "participant_connected",
                    participant_sid=participant.sid,
                    participant_identity=participant.identity
                )
            
            @self.room.on("track_published")
            def on_track_published(
                publication: rtc.RemoteTrackPublication,
                participant: rtc.RemoteParticipant
            ):
                self.logger.info(
                    "track_published",
                    track_sid=publication.sid,
                    participant_sid=participant.sid,
                    track_kind=publication.kind
                )
            
            # Connect
            await self.room.connect(self.config.url, jwt_token)
            
            self.logger.info(
                "agent_joined_room",
                room_name=room_name,
                identity=identity,
                num_participants=len(self.room.remote_participants)
            )
            
            return self.room
            
        except Exception as e:
            self.logger.error(
                "room_join_failed",
                error=str(e),
                room_name=room_name
            )
            raise
    
    async def subscribe_audio(
        self,
        participant_sid: Optional[str] = None,
        on_audio_frame: Optional[Callable] = None
    ) -> AsyncIterator[rtc.AudioFrame]:
        """
        Subscribe to audio from a participant.
        
        Args:
            participant_sid: Specific participant to subscribe to (None for all)
            on_audio_frame: Optional callback for each audio frame
            
        Yields:
            Audio frames from subscribed tracks
        """
        if not self.room:
            raise RuntimeError("Not connected to room. Call join_room_as_agent first.")
        
        self.logger.info(
            "subscribing_to_audio",
            participant_sid=participant_sid or "all"
        )
        
        async def handle_track(track: rtc.Track, participant: rtc.RemoteParticipant):
            """Handle incoming audio track"""
            if track.kind != rtc.TrackKind.KIND_AUDIO:
                return
            
            self.logger.info(
                "audio_track_subscribed",
                track_sid=track.sid,
                participant_sid=participant.sid
            )
            
            audio_stream = rtc.AudioStream(track)
            
            async for frame in audio_stream:
                if on_audio_frame:
                    await on_audio_frame(frame)
                yield frame
        
        # Handle existing participants
        for participant in self.room.remote_participants.values():
            if participant_sid and participant.sid != participant_sid:
                continue
            
            for publication in participant.track_publications.values():
                if publication.track and publication.kind == rtc.TrackKind.KIND_AUDIO:
                    async for frame in handle_track(publication.track, participant):
                        yield frame
        
        # Handle new tracks
        @self.room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant
        ):
            if participant_sid and participant.sid != participant_sid:
                return
            
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                asyncio.create_task(
                    self._process_track(track, participant, on_audio_frame)
                )
    
    async def _process_track(
        self,
        track: rtc.Track,
        participant: rtc.RemoteParticipant,
        callback: Optional[Callable]
    ):
        """Process audio track in background"""
        audio_stream = rtc.AudioStream(track)
        async for frame in audio_stream:
            if callback:
                await callback(frame)
    
    async def publish_audio_chunk(self, audio_data: bytes, sample_rate: int = 16000):
        """
        Publish audio chunk to the room.
        
        Args:
            audio_data: Raw audio bytes (PCM16)
            sample_rate: Audio sample rate (default 16kHz)
        """
        if not self.room:
            raise RuntimeError("Not connected to room. Call join_room_as_agent first.")
        
        try:
            # Create audio source if not exists
            if not self.audio_source:
                self.audio_source = rtc.AudioSource(sample_rate, 1)  # 1 channel (mono)
                
                # Create and publish track
                track = rtc.LocalAudioTrack.create_audio_track(
                    "agent-audio",
                    self.audio_source
                )
                await self.room.local_participant.publish_track(
                    track,
                    rtc.TrackPublishOptions()
                )
                
                self.logger.info("audio_track_published", sample_rate=sample_rate)
            
            # Convert bytes to audio frame and publish
            await self.audio_source.capture_frame(
                rtc.AudioFrame(
                    data=audio_data,
                    sample_rate=sample_rate,
                    num_channels=1,
                    samples_per_channel=len(audio_data) // 2  # 16-bit = 2 bytes per sample
                )
            )
            
        except Exception as e:
            self.logger.error("audio_publish_failed", error=str(e))
            raise
    
    async def disconnect(self):
        """Disconnect from the room"""
        if self.room:
            await self.room.disconnect()
            self.logger.info("disconnected_from_room")
            self.room = None
            self.audio_source = None


class MockLiveKitClient:
    """
    Mock LiveKit client for testing without real LiveKit connection.
    
    Simulates room operations and audio streaming for local development.
    """
    
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.room_name: Optional[str] = None
        self.connected = False
        self.published_audio_chunks = []
        self.logger = logger.bind(call_id=call_id, mode="mock")
    
    async def create_room(self, room_name: str) -> dict:
        """Mock room creation"""
        self.logger.info("mock_room_created", room_name=room_name)
        return {
            "name": room_name,
            "sid": f"mock-room-{room_name}",
            "creation_time": asyncio.get_event_loop().time()
        }
    
    async def join_room_as_agent(
        self,
        room_name: str,
        identity: Optional[str] = None
    ):
        """Mock room join"""
        self.room_name = room_name
        self.connected = True
        identity = identity or f"zylin-agent-{self.call_id}"
        
        self.logger.info(
            "mock_agent_joined_room",
            room_name=room_name,
            identity=identity
        )
        
        return self
    
    async def subscribe_audio(
        self,
        participant_sid: Optional[str] = None,
        on_audio_frame: Optional[Callable] = None
    ) -> AsyncIterator[bytes]:
        """
        Mock audio subscription - yields audio from a test file.
        
        For testing, this can read from a predefined audio file.
        """
        self.logger.info("mock_subscribing_to_audio")
        
        # Simulate empty stream - actual test will inject audio
        if False:  # pylint: disable=using-constant-test
            yield b""
    
    async def publish_audio_chunk(self, audio_data: bytes, sample_rate: int = 16000):
        """Mock audio publishing"""
        self.published_audio_chunks.append({
            "data": audio_data,
            "sample_rate": sample_rate,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        self.logger.debug(
            "mock_audio_published",
            chunk_size=len(audio_data),
            total_chunks=len(self.published_audio_chunks)
        )
    
    async def disconnect(self):
        """Mock disconnect"""
        self.connected = False
        self.logger.info("mock_disconnected_from_room")
    
    def get_published_audio(self) -> list:
        """Get all published audio chunks for testing"""
        return self.published_audio_chunks


def create_livekit_client(call_id: str, use_mock: bool = False) -> LiveKitClient | MockLiveKitClient:
    """
    Factory function to create LiveKit client (real or mock).
    
    Args:
        call_id: Unique call identifier
        use_mock: If True, returns MockLiveKitClient for testing
        
    Returns:
        LiveKit client instance
    """
    if use_mock:
        return MockLiveKitClient(call_id)
    
    config = LiveKitConfig(
        url=os.getenv("LIVEKIT_URL", ""),
        api_key=os.getenv("LIVEKIT_API_KEY", ""),
        api_secret=os.getenv("LIVEKIT_API_SECRET", "")
    )
    
    if not all([config.url, config.api_key, config.api_secret]):
        logger.warning(
            "livekit_config_incomplete",
            message="Using mock client. Set LIVEKIT_* env vars for real connection."
        )
        return MockLiveKitClient(call_id)
    
    return LiveKitClient(config, call_id)
