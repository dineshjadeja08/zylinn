"""
ElevenLabs TTS Validation Script
Tests TTS configuration and generates sample audio
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add agent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agent"))

from adapters.tts_adapter import create_tts_adapter

# Load environment variables
load_dotenv()


async def test_tts():
    """Test TTS configuration and generate sample audio"""
    
    print("=" * 60)
    print("ElevenLabs TTS Validation")
    print("=" * 60)
    
    # Check environment variables
    tts_provider = os.getenv("TTS_PROVIDER", "gtts")
    tts_api_key = os.getenv("TTS_API_KEY", "")
    tts_voice_id = os.getenv("TTS_VOICE_ID", "")
    
    print(f"\n📋 Configuration:")
    print(f"  TTS_PROVIDER: {tts_provider}")
    print(f"  TTS_API_KEY: {'✅ Set' if tts_api_key else '❌ Not set'}")
    print(f"  TTS_VOICE_ID: {tts_voice_id or '(using default)'}")
    
    if tts_provider == "elevenlabs" and not tts_api_key:
        print("\n⚠️  Warning: TTS_PROVIDER is 'elevenlabs' but TTS_API_KEY is not set")
        print("    Will fallback to gTTS (free, lower quality)")
        print("\n💡 To use ElevenLabs:")
        print("    1. Get API key from https://elevenlabs.io/app/settings/api-keys")
        print("    2. Add to .env file: TTS_API_KEY=your_key_here")
        print("    3. Run this script again")
    
    # Create TTS adapter
    print("\n🔧 Creating TTS adapter...")
    try:
        adapter = create_tts_adapter(
            call_id="test-validation",
            use_mock=False
        )
        
        adapter_type = type(adapter).__name__
        print(f"  ✅ Adapter created: {adapter_type}")
        
        if adapter_type == "ElevenLabsTTSAdapter":
            print(f"  🎤 Voice ID: {adapter.voice_id}")
            print(f"  🚀 Model: eleven_turbo_v2 (optimized for real-time)")
        elif adapter_type == "GTTSFallbackAdapter":
            print(f"  ⚠️  Using fallback adapter (free, lower quality)")
            print(f"  💡 Configure ElevenLabs for production-quality TTS")
        
    except Exception as e:
        print(f"  ❌ Failed to create adapter: {e}")
        return
    
    # Test audio generation
    print("\n🎵 Testing audio generation...")
    test_text = "Hello! This is a test of the Zylin AI voice agent. How can I help you today?"
    print(f"  Text: \"{test_text}\"")
    
    try:
        chunk_count = 0
        total_bytes = 0
        
        print("  Generating audio...", end="", flush=True)
        
        async for chunk in adapter.stream_speech(test_text):
            chunk_count += 1
            total_bytes += len(chunk)
            
            # Show progress
            if chunk_count % 10 == 0:
                print(".", end="", flush=True)
        
        print(" Done!")
        
        print(f"\n✅ Audio generated successfully!")
        print(f"  Chunks: {chunk_count}")
        print(f"  Total bytes: {total_bytes:,}")
        print(f"  Format: 16kHz PCM, 16-bit, mono")
        
        # Calculate audio duration
        bytes_per_second = 16000 * 2  # 16kHz * 2 bytes (16-bit)
        duration_seconds = total_bytes / bytes_per_second
        print(f"  Duration: {duration_seconds:.2f} seconds")
        
        # Save sample audio (optional)
        save_sample = os.getenv("SAVE_TTS_SAMPLE", "false").lower() == "true"
        if save_sample:
            output_file = "tts_sample.raw"
            print(f"\n💾 Saving sample to {output_file}...")
            
            # Re-generate to save
            with open(output_file, "wb") as f:
                async for chunk in adapter.stream_speech(test_text):
                    f.write(chunk)
            
            print(f"  ✅ Saved to {output_file}")
            print(f"  Play with: ffplay -f s16le -ar 16000 -ac 1 {output_file}")
        
    except Exception as e:
        print(f"\n  ❌ Audio generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    finally:
        await adapter.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if adapter_type == "ElevenLabsTTSAdapter":
        print("✅ ElevenLabs TTS is configured and working!")
        print("\n📝 Next steps:")
        print("  1. Test with different voices (see ELEVENLABS_TTS_SETUP.md)")
        print("  2. Run agent: python run_persistent_agent.py")
        print("  3. Make a test call to hear the voice")
        print("  4. Monitor costs in ElevenLabs dashboard")
    elif adapter_type == "GTTSFallbackAdapter":
        print("⚠️  Using fallback TTS (gTTS)")
        print("\n📝 To enable ElevenLabs TTS:")
        print("  1. Sign up at https://elevenlabs.io/")
        print("  2. Get API key from Settings > API Keys")
        print("  3. Add to .env: TTS_API_KEY=your_key_here")
        print("  4. Set TTS_PROVIDER=elevenlabs")
        print("  5. Run this script again to validate")
    
    print("\n💡 See ELEVENLABS_TTS_SETUP.md for complete setup guide")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tts())
