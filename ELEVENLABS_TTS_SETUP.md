# ElevenLabs TTS Integration Guide

## Overview

Zylin AI now uses **ElevenLabs** for production-quality text-to-speech, providing natural, expressive voices with low latency for real-time conversations.

## Why ElevenLabs?

- ✅ **Ultra-low latency**: Optimized for real-time voice conversations
- ✅ **Natural voices**: State-of-the-art neural TTS with emotion and intonation
- ✅ **Streaming support**: Audio chunks streamed as they're generated
- ✅ **Multiple voices**: 100+ voices including custom voice cloning
- ✅ **LiveKit compatible**: Outputs 16kHz PCM audio format

## Setup Instructions

### 1. Get Your ElevenLabs API Key

1. Sign up at [ElevenLabs](https://elevenlabs.io/)
2. Navigate to [API Settings](https://elevenlabs.io/app/settings/api-keys)
3. Generate a new API key
4. Copy your API key

### 2. Choose Your Voice

Visit the [Voice Library](https://elevenlabs.io/voice-library) to browse available voices.

**Recommended Voices for Phone Agents:**

| Voice ID | Name | Description | Best For |
|----------|------|-------------|----------|
| `21m00Tcm4TlvDq8ikWAM` | Rachel | Professional, clear, American accent | Business calls, appointments |
| `EXAVITQu4vr4xnSDxMaL` | Bella | Friendly, warm, conversational | Customer service, support |
| `MF3mGyEYCl7XYWbV9V6O` | Elli | Young, energetic, upbeat | Marketing, sales calls |
| `TxGEqnHWrfWFTfGW9XjX` | Josh | Male, deep, authoritative | Professional services |
| `pNInz6obpgDQGcFmaJgB` | Adam | Male, friendly, natural | General purpose |
| `AZnzlk1XvdvUeBnXmlld` | Domi | Female, confident, dynamic | Executive communication |

### 3. Configure Environment Variables

Update your `.env` file:

```bash
# TTS Configuration
TTS_PROVIDER=elevenlabs
TTS_API_KEY=sk_your_elevenlabs_api_key_here
TTS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel (default)
```

### 4. Install Dependencies

```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install ElevenLabs SDK
pip install elevenlabs>=1.0.0
```

### 5. Test Your Configuration

```bash
python quick_test.py
```

The test should show:
```
✅ TTS Provider: elevenlabs
✅ Voice ID: 21m00Tcm4TlvDq8ikWAM
```

## Technical Details

### Audio Format

ElevenLabs TTS adapter outputs audio in the format required by LiveKit:

- **Sample Rate**: 16kHz (16,000 Hz)
- **Bit Depth**: 16-bit
- **Channels**: Mono (1 channel)
- **Format**: PCM (Pulse Code Modulation)
- **Encoding**: Raw PCM bytes

### Model Selection

The adapter uses **`eleven_turbo_v2`** model by default:

- **Latency**: ~300-500ms (fastest model)
- **Quality**: High-quality neural synthesis
- **Cost**: $0.18 per 1000 characters (paid plan)
- **Best for**: Real-time voice conversations

Alternative models:
- `eleven_multilingual_v2`: For multi-language support (slower)
- `eleven_monolingual_v1`: Original model (good quality, slower)

### Streaming Behavior

```python
async for audio_chunk in tts_adapter.stream_speech(text):
    # Each chunk is ~50-200ms of audio
    # Chunks are streamed as they're generated
    # No need to wait for full audio generation
    await livekit_client.publish_audio(audio_chunk)
```

## Usage in Agent

The agent automatically uses ElevenLabs when configured:

```python
from agent.adapters.tts_adapter import create_tts_adapter

# In production (use_mock=False)
tts_adapter = create_tts_adapter(call_id, use_mock=False)

# TTS adapter reads TTS_PROVIDER from environment
# If TTS_PROVIDER=elevenlabs and TTS_API_KEY is set, uses ElevenLabs
# Otherwise falls back to gTTS (free, lower quality)
```

## Fallback Strategy

The TTS system has automatic fallback:

```
1. ElevenLabs (if API key configured)
   ↓ (if fails or not configured)
2. Azure TTS (if Azure credentials configured)
   ↓ (if fails or not configured)
3. gTTS (Google Text-to-Speech) - Always available, free
   ↓ (if fails)
4. MockTTS (silent audio for testing)
```

## Cost Estimation

ElevenLabs pricing (as of December 2024):

| Plan | Price | Characters/month | Cost per call* |
|------|-------|------------------|----------------|
| Free | $0 | 10,000 | Limited testing |
| Starter | $5 | 30,000 | ~$0.03 |
| Creator | $22 | 100,000 | ~$0.025 |
| Pro | $99 | 500,000 | ~$0.018 |
| Scale | $330 | 2,000,000 | ~$0.015 |

*Estimated for 2-minute conversation with 300 words (1500 characters)

## Monitoring

The agent logs TTS metrics to Prometheus:

```python
# Metrics tracked:
- tts_request_count: Number of TTS requests
- tts_latency_seconds: Time to first audio chunk
- tts_audio_duration_seconds: Total audio duration generated
- tts_error_count: Number of TTS failures
```

View metrics in Grafana dashboard:
- URL: http://localhost:3000
- Dashboard: "Zylin AI Agent Metrics"
- Panel: "TTS Performance"

## Troubleshooting

### Issue: "elevenlabs package not installed"

**Solution:**
```bash
pip install elevenlabs>=1.0.0
```

### Issue: "ElevenLabs API key missing"

**Solution:**
1. Check `.env` file has `TTS_API_KEY=sk_...`
2. Verify API key is valid at https://elevenlabs.io/app/settings/api-keys
3. Restart the agent after updating `.env`

### Issue: "Voice not found"

**Solution:**
1. Verify `TTS_VOICE_ID` matches a valid voice ID
2. List available voices:
```python
from elevenlabs import voices
available = voices()
for voice in available:
    print(f"{voice.voice_id}: {voice.name}")
```

### Issue: Audio sounds distorted

**Solution:**
1. Check that `output_format="pcm_16000"` is set (already configured)
2. Verify LiveKit is expecting 16kHz PCM audio
3. Check network latency - high latency may cause buffering issues

### Issue: High latency (slow responses)

**Solution:**
1. Ensure using `eleven_turbo_v2` model (already configured)
2. Check network connection to ElevenLabs API
3. Consider switching to a closer Azure region for Azure TTS fallback
4. Monitor Prometheus metrics for actual latency numbers

## Custom Voice Cloning

ElevenLabs supports custom voice cloning for brand consistency:

1. Upload voice samples (1+ minutes of clear audio)
2. Train custom voice model
3. Use custom voice ID in `TTS_VOICE_ID`

See: https://elevenlabs.io/voice-cloning

## Production Checklist

Before deploying to production:

- [ ] ElevenLabs API key configured in secrets vault (not .env)
- [ ] Voice ID tested and approved by stakeholders
- [ ] Fallback TTS provider configured (Azure or gTTS)
- [ ] TTS metrics monitored in Grafana
- [ ] Cost alerts configured for ElevenLabs usage
- [ ] Rate limiting implemented (if using free tier)
- [ ] Error handling tested (simulate API failures)
- [ ] Audio quality verified on real phone calls
- [ ] Latency acceptable (<1 second for first audio chunk)

## Migration from Mock TTS

If you're currently using `MockTTSAdapter`:

**Before:**
```python
tts_adapter = create_tts_adapter(call_id, use_mock=True)
# Silent audio only
```

**After:**
```python
# Set in .env:
# TTS_PROVIDER=elevenlabs
# TTS_API_KEY=sk_...

tts_adapter = create_tts_adapter(call_id, use_mock=False)
# Real voice output with natural intonation
```

## Support

- **ElevenLabs Docs**: https://docs.elevenlabs.io/
- **API Reference**: https://docs.elevenlabs.io/api-reference/
- **Discord Community**: https://discord.gg/elevenlabs
- **Support Email**: support@elevenlabs.io

## Next Steps

1. ✅ **Complete this setup** - Configure ElevenLabs API key
2. 🔄 **Test voice quality** - Make test calls with different voices
3. 🔐 **Migrate to secrets vault** - Move API key from .env to vault (Task #3)
4. 📊 **Monitor costs** - Set up billing alerts in ElevenLabs dashboard
5. 🚀 **Deploy to production** - Update production environment with credentials
