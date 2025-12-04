# Zylin Voice Agent - Quick Runbook

## 🚀 Demo Call Setup (5 minutes)

### Step 1: Environment Setup

```powershell
# Navigate to project
cd c:\Users\VIKNESH B\OneDrive\Desktop\zylinn

# Copy environment file
cp .env.example .env

# Edit .env - For demo, leave defaults (will use mock adapters)
```

### Step 2: Start Backend

```powershell
# Open Terminal 1
cd backend\scripts
.\start-backend.ps1
```

Expected output:
```
🚀 Starting Zylin Backend API...
📝 Loading environment variables from .env
✅ Starting FastAPI server on port 8000...
INFO: Uvicorn running on http://0.0.0.0:8000
```

Verify: Open browser to http://localhost:8000 - should see API status

### Step 3: Run Demo Simulation

```powershell
# Open Terminal 2
cd agent\scripts
.\simulate-audio-call.ps1
```

Expected output:
```
🎙️ Simulating Audio Call...
📞 Simulating call: test-call-xxxxxxxx in room: test-room
✅ Call record created
📝 Transcript: Hello, can you hear me?
🤖 Agent response: You said: Hello, can you hear me?
🔊 Published X audio chunks
...
✅ SIMULATION PASSED:
   - 3 transcript(s) saved
   - 3 agent reply/replies saved
```

### Step 4: Verify Database Records

```powershell
# Check API for results
curl http://localhost:8000/calls

# Get specific call details
curl http://localhost:8000/calls/test-call-xxxxxxxx
```

### Step 5: Run Tests

```powershell
# Install test dependencies
pip install -r tests\requirements.txt

# Run all tests
pytest -v

# Run specific test suites
pytest tests\unit\ -v          # Unit tests only
pytest tests\integration\ -v   # Integration tests only
```

---

## 🎭 Running with Mock Adapters (No API Keys Required)

Perfect for development and testing:

```powershell
# Start agent in mock mode
cd agent\scripts
.\start-agent.ps1 -Room "demo-room" -Mock
```

This uses:
- Mock STT (predefined transcripts)
- Mock LLM (simple echo responses)
- Mock TTS (silent audio)
- Mock LiveKit (no real connection)

---

## 🔴 Running with Real APIs

### Prerequisites:
1. LiveKit account (https://livekit.io)
2. OpenAI API key (https://platform.openai.com)
3. (Optional) AssemblyAI, ElevenLabs keys

### Configuration:

Edit `.env`:
```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
STT_PROVIDER=assemblyai
STT_API_KEY=xxxxxxxxxxxxxxxx
TTS_PROVIDER=elevenlabs
TTS_API_KEY=xxxxxxxxxxxxxxxx
```

### Start Agent:

```powershell
# Without mock flag - uses real providers
cd agent\scripts
.\start-agent.ps1 -Room "production-room-123"
```

---

## 📊 Acceptance Test Checklist

Run these to verify MVP acceptance criteria:

### ✅ Test 1: Backend Starts
```powershell
cd backend\scripts
.\start-backend.ps1
```
**Success**: Server starts on port 8000, no errors

### ✅ Test 2: Agent Can Start
```powershell
cd agent\scripts
.\start-agent.ps1 -Room "test" -Mock
```
**Success**: Agent connects, shows "agent_joined_room" log

### ✅ Test 3: Simulation Produces DB Records
```powershell
cd agent\scripts
.\simulate-audio-call.ps1
```
**Success**: Output shows "SIMULATION PASSED" with transcript/reply counts

### ✅ Test 4: Unit Tests Pass
```powershell
pytest tests\unit\ -v
```
**Success**: All tests pass, no failures

---

## 🐛 Troubleshooting

### "Module not found" errors
```powershell
# Ensure you're in virtual environment
cd agent  # or backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Port 8000 already in use
```powershell
# Change port in .env
$env:BACKEND_PORT="8001"
# Then restart backend
```

### Database locked errors
```bash
# Use PostgreSQL instead
DATABASE_URL=postgresql://user:pass@localhost/zylin
```

---

## 📈 Monitoring Logs

All components use structured JSON logging:

```powershell
# View agent logs
cd agent
python agent.py --room "test" --mock --log-level DEBUG

# View backend logs
cd backend
# Logs appear in terminal where uvicorn is running
```

Log format:
```json
{
  "event": "transcript_received",
  "call_id": "call-abc123",
  "text": "Hello world",
  "is_final": true,
  "timestamp": "2025-12-04T10:30:00Z"
}
```

---

## 🔄 Common Development Workflow

1. **Make code changes**
2. **Run unit tests**: `pytest tests/unit/`
3. **Run simulation**: `.\agent\scripts\simulate-audio-call.ps1`
4. **Check DB**: `curl http://localhost:8000/calls`
5. **Commit**: `git add . && git commit -m "feat: description"`
6. **Push**: `git push origin main`
7. **CI runs automatically** on GitHub

---

## 📦 Docker Quick Start

```powershell
# Build images
cd agent
docker build -t zylin-agent .

cd ..\backend
docker build -t zylin-backend .

# Run backend
docker run -p 8000:8000 `
  -e DATABASE_URL=sqlite:///./zylin.db `
  zylin-backend

# Run agent
docker run `
  -e LIVEKIT_URL=$env:LIVEKIT_URL `
  -e OPENAI_API_KEY=$env:OPENAI_API_KEY `
  zylin-agent --room "docker-test" --mock
```

---

## 🎯 Next Steps

1. **Get API Keys**: Sign up for LiveKit, OpenAI, etc.
2. **Test Real Call**: Connect with actual audio
3. **Deploy**: Use Docker or cloud platform
4. **Monitor**: Set up logging/metrics
5. **Scale**: Add more agent instances

---

## 📞 Quick Test Call Flow

```
User speaks → LiveKit captures audio → Agent receives
    ↓
STT transcribes → "Hello, I need help"
    ↓
LLM processes → "I'm here to help! What do you need?"
    ↓
TTS synthesizes → Audio stream
    ↓
LiveKit publishes → User hears response
```

Total latency: ~1-2 seconds end-to-end

---

**Ready to demo! 🎉**
