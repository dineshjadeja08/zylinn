"""
Zylin Voice Agent - Test Caller
Generates a LiveKit token and opens the test client in browser
"""
import os
import sys
import webbrowser
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from livekit import api
except ImportError:
    print("❌ Error: livekit-api package not installed")
    print("Run: pip install livekit-api")
    sys.exit(1)

def generate_token(room_name: str, participant_name: str) -> str:
    """Generate LiveKit access token"""
    load_dotenv()
    
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")
    
    if not all([api_key, api_secret, livekit_url]):
        print("❌ Error: Missing LiveKit credentials in .env file")
        print("Required: LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL")
        sys.exit(1)
    
    # Create token
    token = api.AccessToken(api_key, api_secret) \
        .with_identity(participant_name) \
        .with_name(participant_name) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        )).to_jwt()
    
    return token

def create_test_page(token: str, room_name: str):
    """Create HTML test page with embedded token"""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zylin Voice Agent - Test Call</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 600px;
            margin: 50px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #667eea;
            text-align: center;
            margin-bottom: 10px;
        }}
        button {{
            width: 100%;
            padding: 15px;
            font-size: 18px;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            margin: 10px 0;
            transition: all 0.3s;
        }}
        #startBtn {{
            background: #667eea;
            color: white;
        }}
        #startBtn:hover {{
            background: #5568d3;
            transform: translateY(-2px);
        }}
        #endBtn {{
            background: #f56565;
            color: white;
            display: none;
        }}
        #endBtn:hover {{
            background: #e53e3e;
        }}
        .status {{
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            text-align: center;
            font-weight: 500;
        }}
        .mic {{
            font-size: 64px;
            text-align: center;
            margin: 20px 0;
            display: none;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ Zylin Voice Agent</h1>
        <p style="text-align: center; color: #666;">Room: <strong>{room_name}</strong></p>
        
        <button id="startBtn" onclick="startCall()">🚀 Start Call with Agent</button>
        <button id="endBtn" onclick="endCall()">📞 End Call</button>
        
        <div class="mic" id="mic">🎤</div>
        <div class="status" id="status">Click "Start Call" to begin</div>
    </div>

    <script type="module">
        import * as LK from 'https://cdn.jsdelivr.net/npm/livekit-client@2.5.8/+esm';
        
        const LIVEKIT_URL = '{os.getenv("LIVEKIT_URL")}';
        const TOKEN = '{token}';
        let room = null;
        let audioTrack = null;
        
        // Make functions globally accessible
        window.startCall = startCall;
        window.endCall = endCall;

        function updateStatus(msg, color = '#667eea') {{
            const status = document.getElementById('status');
            status.textContent = msg;
            status.style.background = color;
            status.style.color = 'white';
        }}

        async function startCall() {{
            try {{
                document.getElementById('startBtn').style.display = 'none';
                updateStatus('🔌 Connecting...', '#ffa500');

                // Create room
                room = new LK.Room({{
                    adaptiveStream: true,
                    dynacast: true,
                }});

                // Room events
                room.on(LK.RoomEvent.Connected, async () => {{
                    updateStatus('✅ Connected! Speak to the agent...', '#48bb78');
                    document.getElementById('mic').style.display = 'block';
                    document.getElementById('endBtn').style.display = 'block';

                    // Publish microphone
                    audioTrack = await LK.createLocalAudioTrack({{
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    }});
                    await room.localParticipant.publishTrack(audioTrack);
                }});

                room.on(LK.RoomEvent.TrackSubscribed, (track, publication, participant) => {{
                    if (track.kind === LK.Track.Kind.Audio) {{
                        const audio = track.attach();
                        document.body.appendChild(audio);
                        updateStatus('🔊 Agent audio connected - listening...', '#667eea');
                    }}
                }});

                room.on(LK.RoomEvent.Disconnected, () => {{
                    updateStatus('📴 Disconnected', '#f56565');
                    cleanup();
                }});

                room.on(LK.RoomEvent.ParticipantConnected, (participant) => {{
                    if (participant.identity.includes('agent')) {{
                        updateStatus('🤖 Agent joined! Start speaking...', '#48bb78');
                    }}
                }});

                // Connect
                await room.connect(LIVEKIT_URL, TOKEN);

            }} catch (error) {{
                updateStatus('❌ Error: ' + error.message, '#f56565');
                console.error(error);
                document.getElementById('startBtn').style.display = 'block';
            }}
        }}

        async function endCall() {{
            if (room) {{
                await room.disconnect();
            }}
            cleanup();
        }}

        function cleanup() {{
            if (audioTrack) {{
                audioTrack.stop();
                audioTrack = null;
            }}
            room = null;
            document.getElementById('startBtn').style.display = 'block';
            document.getElementById('endBtn').style.display = 'none';
            document.getElementById('mic').style.display = 'none';
            updateStatus('Click "Start Call" to begin', '#667eea');
        }}
    </script>
</body>
</html>"""
    
    # Save to temp file
    temp_file = Path(__file__).parent / "test_call_temp.html"
    temp_file.write_text(html_content, encoding='utf-8')
    return temp_file

def main():
    print("🎙️ Zylin Voice Agent - Test Call Generator\n")
    
    # Accept room name from command line or prompt
    import sys
    if len(sys.argv) > 1:
        room_name = sys.argv[1]
    else:
        room_name = input("Enter room name [test-room-001]: ").strip() or "test-room-001"
    participant_name = f"test-caller-{os.getpid()}"
    
    print(f"\n📝 Generating token for room: {room_name}")
    print(f"👤 Participant: {participant_name}")
    
    try:
        token = generate_token(room_name, participant_name)
        print("✅ Token generated successfully!")
        
        print("\n🌐 Creating test page...")
        test_page = create_test_page(token, room_name)
        
        print(f"✅ Test page created: {test_page}")
        print("\n🚀 Opening in browser...")
        print("\n" + "="*60)
        print("INSTRUCTIONS:")
        print("="*60)
        print("1. Make sure the agent is running:")
        print(f"   python agent/agent.py --room {room_name}")
        print("\n2. Click 'Start Call' in the browser")
        print("3. Allow microphone access when prompted")
        print("4. Start speaking to the agent!")
        print("="*60 + "\n")
        
        webbrowser.open(test_page.as_uri())
        
        input("Press Enter to close...")
        
        # Cleanup
        if test_page.exists():
            test_page.unlink()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
