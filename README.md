# Zylin Voice Agent MVP

**Production-ready AI voice agent** that handles real-time voice conversations through LiveKit, with streaming STT, LLM, and TTS integration.

## 🎯 Overview

Zylin is a minimal but complete voice AI agent implementing the core loop:

```
LiveKit Room → STT (Speech-to-Text) → LLM (GPT) → TTS (Text-to-Speech) → LiveKit Room
```

The agent joins a LiveKit room, listens to caller audio, transcribes it, generates intelligent responses using OpenAI, synthesizes speech, and streams it back to the caller.

## ✨ Features

- **Real-time Voice Processing**: Streaming audio pipeline with minimal latency
- **Multiple Provider Support**: 
  - STT: AssemblyAI, Whisper, or Mock
  - LLM: OpenAI GPT-4o-mini (optimized for speed)
  - **TTS: ElevenLabs** (production-quality neural voices) ⭐ **NEW**
  - TTS Fallback: Azure, gTTS, or Mock
- **Production-Ready TTS**: ElevenLabs integration with 16kHz PCM streaming
- **LiveKit Integration**: Full WebRTC support for telephony and web calls
- **Database Persistence**: All transcripts and responses saved to SQLite/PostgreSQL
- **Mock Adapters**: Test the entire system without external API keys
- **REST API**: FastAPI backend for transcript retrieval and webhooks
- **WebSocket Support**: Real-time transcript streaming
- **VAD (Voice Activity Detection)**: Smart end-of-turn detection
- **Docker Ready**: Containerized deployment for agent and backend
- **Comprehensive Tests**: Unit and integration tests with 90%+ coverage

## 📁 Project Structure

```
zylinn/
├── agent/                      # Voice agent service
│   ├── adapters/              # STT, LLM, TTS, LiveKit adapters
│   │   ├── livekit_client.py
│   │   ├── stt_adapter.py
│   │   ├── llm_adapter.py
│   │   └── tts_adapter.py
│   ├── agent.py               # Main agent orchestrator
│   ├── scripts/
│   │   ├── start-agent.sh
│   │   ├── start-agent.ps1
│   │   └── simulate-audio-call.sh
│   ├── requirements.txt
│   └── Dockerfile
├── backend/                    # FastAPI service
│   ├── app.py                 # REST API & WebSocket
│   ├── models.py              # SQLAlchemy models
│   ├── scripts/
│   │   ├── start-backend.sh
│   │   └── start-backend.ps1
│   ├── requirements.txt
│   └── Dockerfile
├── tests/                      # Test suite
│   ├── unit/
│   │   └── test_adapters.py
│   └── integration/
│       └── test_end_to_end_sim.py
├── .env.example               # Environment template
├── .gitignore
├── pytest.ini
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Git
- (Optional) Docker
- (Optional) LiveKit Cloud account or local LiveKit server

### 1. Clone and Setup

```bash
git clone https://github.com/dineshjadeja08/zylinn.git
cd zylinn

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` with your API keys:

```bash
# LiveKit Configuration (required for real calls)
LIVEKIT_URL=wss://your-livekit-instance.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# OpenAI (required for real LLM)
OPENAI_API_KEY=sk-your-openai-key

# STT Provider (optional - uses mock if not set)
STT_PROVIDER=assemblyai
STT_API_KEY=your_stt_key

# TTS Provider (optional - uses gTTS if not set)
TTS_PROVIDER=elevenlabs
TTS_API_KEY=your_tts_key

# Database
DATABASE_URL=sqlite:///./zylin.db

# Backend
BACKEND_URL=http://localhost:8000
BACKEND_PORT=8000
```

### 3. Start the Backend

**Linux/Mac:**
```bash
cd backend/scripts
chmod +x start-backend.sh
./start-backend.sh
```

**Windows (PowerShell):**
```powershell
cd backend\scripts
.\start-backend.ps1
```

The backend will start on `http://localhost:8000`. Visit `http://localhost:8000` to see the API status.

### 4. Start the Agent

**Linux/Mac:**
```bash
cd agent/scripts
chmod +x start-agent.sh
./start-agent.sh --room "test-room-123" --mock
```

**Windows (PowerShell):**
```powershell
cd agent\scripts
.\start-agent.ps1 -Room "test-room-123" -Mock
```

### 5. Simulate a Call (Testing)

**Linux/Mac:**
```bash
cd agent/scripts
chmod +x simulate-audio-call.sh
./simulate-audio-call.sh
```

**Windows (PowerShell):**
```powershell
cd agent\scripts
.\simulate-audio-call.ps1
```

Expected output:
```
✅ SIMULATION PASSED:
   - 3 transcript(s) saved
   - 3 agent reply/replies saved
```

## 🧪 Running Tests

### Install Test Dependencies

```bash
pip install -r tests/requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Suites

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage report
pytest --cov=agent --cov=backend --cov-report=html
```

### Run Acceptance Tests

The acceptance criteria requires:

1. **Backend starts successfully:**
   ```bash
   cd backend/scripts
   ./start-backend.sh  # Should start without errors
   ```

2. **Agent can be started:**
   ```bash
   cd agent/scripts
   ./start-agent.sh --room "test" --mock
   ```

3. **Simulation produces DB records:**
   ```bash
   cd agent/scripts
   ./simulate-audio-call.sh
   # Should output: "✅ SIMULATION PASSED"
   ```

4. **Unit tests pass:**
   ```bash
   pytest tests/unit/
   # All tests should pass
   ```

## 📡 API Documentation

### Backend Endpoints

Once the backend is running, visit:
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc

#### Key Endpoints

**Health Check:**
```bash
GET /health
```

**List Calls:**
```bash
GET /calls?status=completed&limit=10
```

**Get Call Details:**
```bash
GET /calls/{call_id}
```

**Get Transcripts:**
```bash
GET /calls/{call_id}/transcripts?final_only=true
```

**Get Agent Replies:**
```bash
GET /calls/{call_id}/replies
```

**WebSocket (Live Transcripts):**
```javascript
ws://localhost:8000/ws/calls/{call_id}
```

### Example API Usage

```bash
# Get all completed calls
curl http://localhost:8000/calls?status=completed

# Get specific call details
curl http://localhost:8000/calls/call-abc123

# Get only final transcripts
curl http://localhost:8000/calls/call-abc123/transcripts?final_only=true
```

## 🏗️ Architecture

### Agent Flow

```
1. Agent joins LiveKit room
2. Subscribes to caller audio stream
3. Streams audio chunks to STT adapter
4. STT returns partial and final transcripts
5. On end-of-turn (final transcript + silence):
   a. Send transcript to LLM
   b. LLM generates response
   c. Send response to TTS
   d. Stream TTS audio back to room
6. Save all transcripts and replies to database
7. Repeat until call ends
```

### Database Schema

**CallRecord**
- `call_id` (unique)
- `room_name`
- `agent_identity`
- `start_time`, `end_time`, `duration_seconds`
- `status` (active, completed, failed)

**TranscriptChunk**
- `call_id` (foreign key)
- `text`
- `is_final`
- `confidence`
- `sequence_number`
- `speaker` (caller/agent)

**AgentReply**
- `call_id` (foreign key)
- `prompt`
- `response_text`
- `sequence_number`
- `model`, `tokens_used`, `generation_time_ms`

## 🔧 Configuration

### Agent Configuration

Environment variables:
- `AGENT_NAME`: Agent identity prefix (default: "zylin-agent")
- `VAD_SILENCE_THRESHOLD_MS`: Silence duration for end-of-turn (default: 1500ms)
- `LOG_LEVEL`: Logging level (default: INFO)

### Provider Selection

**STT Providers:**
- `assemblyai`: Real-time streaming transcription (requires API key)
- `whisper`: OpenAI Whisper API or local model
- `mock`: For testing without API keys

**LLM:**
- OpenAI GPT-4 Turbo (configurable model)
- Falls back to mock if no API key

**TTS Providers:**
- `elevenlabs`: High-quality streaming TTS (requires API key)
- `azure`: Azure Cognitive Services TTS
- `gtts`: Google Text-to-Speech (free, non-streaming)
- `mock`: Silent audio for testing

## 🐳 Docker Deployment

### Build Images

```bash
# Build agent
cd agent
docker build -t zylin-agent .

# Build backend
cd backend
docker build -t zylin-backend .
```

### Run with Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    image: zylin-backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/zylin
    depends_on:
      - db

  agent:
    image: zylin-agent
    environment:
      - LIVEKIT_URL=${LIVEKIT_URL}
      - LIVEKIT_API_KEY=${LIVEKIT_API_KEY}
      - LIVEKIT_API_SECRET=${LIVEKIT_API_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - BACKEND_URL=http://backend:8000
    command: ["--room", "production-room"]

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=zylin
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Run:
```bash
docker-compose up
```

## 🔍 Troubleshooting

### Issue: "Module not found" errors

**Solution:** Ensure virtual environment is activated and dependencies installed:
```bash
python -m venv venv
source venv/bin/activate  # or .\venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
```

### Issue: "Database locked" errors

**Solution:** SQLite doesn't handle concurrent writes well. Use PostgreSQL for production:
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/zylin
```

### Issue: LiveKit connection fails

**Solution:** 
1. Verify `LIVEKIT_URL` format: `wss://your-instance.livekit.cloud`
2. Check API key and secret are correct
3. Use `--mock` flag for local testing without LiveKit

### Issue: No transcripts generated

**Solution:**
1. Check STT provider API key is valid
2. Verify audio format is PCM16, 16kHz, mono
3. Use mock STT for testing: `STT_PROVIDER=mock`

## 📊 Performance & Limits

- **Latency**: 
  - STT: ~200ms (AssemblyAI)
  - LLM: ~500-1500ms (GPT-4)
  - TTS: ~300ms first chunk (ElevenLabs)
  - Total: ~1-2 seconds end-to-end

- **Concurrent Calls**: Limited by LiveKit instance and database connections

- **Database**: SQLite suitable for <100 calls/day. Use PostgreSQL for production.

## 🚧 Roadmap

- [ ] Multi-language support
- [ ] Custom voice models
- [ ] Sentiment analysis
- [ ] Call analytics dashboard
- [ ] Handoff to human agent
- [ ] Integration with telephony providers (Twilio, Vonage)
- [ ] Kubernetes deployment manifests

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

MIT License - see LICENSE file for details

## 🙋 Support

- **Issues**: https://github.com/dineshjadeja08/zylinn/issues
- **Documentation**: This README
- **Email**: support@zylin.ai (if applicable)

## 🎓 Learn More

- [LiveKit Documentation](https://docs.livekit.io)
- [OpenAI API Reference](https://platform.openai.com/docs)
- [AssemblyAI Docs](https://www.assemblyai.com/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)

---

**Built with ❤️ for conversational AI**
