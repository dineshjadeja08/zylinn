"""
Simple test script to join a LiveKit room and test the Zylin agent.
This simulates a caller joining the room with audio.
"""
import asyncio
import os
from dotenv import load_dotenv
from livekit import rtc, api
import wave
import struct
import math

load_dotenv()

async def generate_test_audio(duration_seconds=5, frequency=440):
    """Generate a simple sine wave test tone"""
    sample_rate = 16000
    num_samples = duration_seconds * sample_rate
    
    audio_data = []
    for i in range(num_samples):
        # Generate sine wave
        sample = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * i / sample_rate))
        audio_data.append(struct.pack('<h', sample))
    
    return b''.join(audio_data)

async def test_call():
    """Join the LiveKit room and send test audio"""
    print("🎙️  Starting test call to Zylin agent...")
    
    # Get LiveKit credentials
    livekit_url = os.getenv("LIVEKIT_URL")
    livekit_api_key = os.getenv("LIVEKIT_API_KEY")
    livekit_api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    room_name = "test-room-001"
    
    # Create room token
    token_generator = api.AccessToken(livekit_api_key, livekit_api_secret)
    token_generator.with_identity("test-caller").with_name("Test Caller").with_grants(
        api.VideoGrants(room_join=True, room=room_name)
    )
    token = token_generator.to_jwt()
    
    print(f"✅ Generated access token")
    print(f"🔗 Connecting to room: {room_name}")
    
    # Connect to room
    room = rtc.Room()
    
    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        print(f"👤 Participant joined: {participant.identity}")
    
    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        print(f"🎵 Subscribed to {participant.identity}'s track: {publication.sid}")
        if isinstance(track, rtc.RemoteAudioTrack):
            print(f"🔊 Receiving audio from agent!")
    
    try:
        # Connect to the room
        await room.connect(livekit_url, token)
        print(f"✅ Connected to room: {room_name}")
        print(f"👥 Participants in room: {len(room.remote_participants)}")
        
        # List participants
        for participant in room.remote_participants.values():
            print(f"   - {participant.identity}")
        
        # Create audio source
        source = rtc.AudioSource(sample_rate=16000, num_channels=1)
        track = rtc.LocalAudioTrack.create_audio_track("test-audio", source)
        
        # Publish audio track
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        publication = await room.local_participant.publish_track(track, options)
        print(f"🎤 Published audio track: {publication.sid}")
        
        # Send test audio (sine wave tone)
        print("🎵 Sending test audio (speaking: 'Hello Zylin, this is a test call')...")
        
        # In a real scenario, you'd send actual speech audio
        # For now, just send a tone to verify audio is flowing
        test_audio = await generate_test_audio(duration_seconds=3, frequency=440)
        
        # Send audio in chunks
        chunk_size = 1600  # 0.1 seconds at 16kHz
        for i in range(0, len(test_audio), chunk_size):
            chunk = test_audio[i:i+chunk_size]
            if len(chunk) == chunk_size:
                # Convert to int16 array
                samples = struct.unpack(f'<{len(chunk)//2}h', chunk)
                audio_frame = rtc.AudioFrame(
                    data=chunk,
                    sample_rate=16000,
                    num_channels=1,
                    samples_per_channel=len(samples)
                )
                await source.capture_frame(audio_frame)
                await asyncio.sleep(0.1)  # 100ms chunks
        
        print("✅ Test audio sent!")
        print("⏳ Waiting for agent response (10 seconds)...")
        await asyncio.sleep(10)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await room.disconnect()
        print("👋 Disconnected from room")

if __name__ == "__main__":
    asyncio.run(test_call())
