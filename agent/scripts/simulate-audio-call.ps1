# Simulate Audio Call (PowerShell)
# Usage: .\simulate-audio-call.ps1 [-AudioFile "path/to/audio.wav"] [-CallId "test-123"] [-Room "test-room"]

param(
    [string]$AudioFile,
    [string]$CallId = "test-call-$(Get-Date -Format 'yyyyMMddHHmmss')",
    [string]$Room = "test-room"
)

Write-Host "Simulating Audio Call..." -ForegroundColor Green

Set-Location $PSScriptRoot\..

if (Test-Path "..\.env") {
    Get-Content "..\.env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*?)\s*=\s*(.*?)\s*$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

if (-not (Test-Path "venv")) {
    python -m venv venv
}

& .\venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

# Create Python simulation script inline
$simScript = @'
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from adapters.livekit_client import MockLiveKitClient
from adapters.stt_adapter import MockSTTAdapter
from adapters.llm_adapter import MockLLMAdapter
from adapters.tts_adapter import MockTTSAdapter
from models import (DatabaseManager, create_call_record, add_transcript_chunk, 
                   add_agent_reply, update_call_status, get_call_record, 
                   get_call_transcripts, get_call_replies)

async def simulate():
    call_id = sys.argv[1]
    room = sys.argv[2]
    
    print(f"Simulating call: {call_id} in room: {room}")
    
    mock_transcripts = [
        "Hello, can you hear me?",
        "I need help with my account.",
        "My account number is 12345."
    ]
    
    db_manager = DatabaseManager()
    db_manager.create_tables()
    
    livekit = MockLiveKitClient(call_id)
    stt = MockSTTAdapter(call_id, mock_transcripts=mock_transcripts)
    llm = MockLLMAdapter(call_id)
    tts = MockTTSAdapter(call_id)
    
    await livekit.join_room_as_agent(room, f"zylin-agent-{call_id}")
    
    session = db_manager.get_session()
    try:
        create_call_record(session, call_id, room, f"zylin-agent-{call_id}")
        print("Call record created")
        
        seq = 0
        for transcript_text in mock_transcripts:
            fake_audio = b'\x00' * 16000
            await stt.send_audio_chunk(fake_audio)
            
            async for transcript in stt.get_transcript_stream():
                if transcript.is_final:
                    print(f"Transcript: {transcript.text}")
                    add_transcript_chunk(session, call_id, transcript.text, True, transcript.confidence, seq)
                    seq += 1
                    
                    response = await llm.generate(transcript.text)
                    print(f"Agent response: {response}")
                    add_agent_reply(session, call_id, transcript.text, response, seq)
                    seq += 1
                    
                    async for chunk in tts.stream_speech(response):
                        await livekit.publish_audio_chunk(chunk)
                    break
        
        update_call_status(session, call_id, "completed")
        print("Call completed")
    finally:
        session.close()
    
    session = db_manager.get_session()
    try:
        call = get_call_record(session, call_id)
        transcripts = get_call_transcripts(session, call_id, final_only=True)
        replies = get_call_replies(session, call_id)
        
        print(f"Call status: {call.status}")
        print(f"Transcripts: {len(transcripts)}")
        print(f"Agent replies: {len(replies)}")
        
        return len(transcripts) > 0 and len(replies) > 0
    finally:
        session.close()

if __name__ == "__main__":
    success = asyncio.run(simulate())
    sys.exit(0 if success else 1)
'@

$simScript | Out-File -FilePath "simulate_call_temp.py" -Encoding UTF8

Write-Host "Running simulation..." -ForegroundColor Cyan
python simulate_call_temp.py $CallId $Room

Remove-Item "simulate_call_temp.py"

Write-Host "Simulation complete!" -ForegroundColor Green
