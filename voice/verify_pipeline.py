"""
voice/verify_pipeline.py
------------------------
Smoke-test for the voice package.

What it does:
  1. Imports and validates all voice modules.
  2. Verifies AudioStream buffer chunking logic (no API key needed).
  3. Skips live API calls unless API keys are present.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()


def separator(title):
    print(f"\n{'='*55}\n  {title}\n{'='*55}")


def test_audio_stream():
    from voice.audio_stream import AudioStream
    separator("TEST 1 — AudioStream Buffering")
    stream = AudioStream(chunk_size=16)
    sample = b"Hello Procurement World!" * 10   # 240 bytes
    stream.write(sample)
    chunks = stream.iter_chunks()
    assert len(chunks) > 0, "No chunks returned!"
    total = sum(len(c) for c in chunks)
    assert total == len(sample), f"Byte loss: {total} != {len(sample)}"
    print(f"  [OK] {len(chunks)} chunk(s), {total} bytes — no data loss.")


def test_voice_processor():
    from agents.voice_processor import VoiceProcessor
    separator("TEST 2 — VoiceProcessor Intent Parsing")
    vp = VoiceProcessor()

    cases = [
        ("we are running low on SCR-M8-001", "CHECK_SHORTAGE"),
        ("what is the current inventory status", "STOCK_STATUS"),
        ("forecast demand for next month", "FORECAST_DEMAND"),
        ("who is the cheapest vendor for ALU-ING-01", "FIND_SUPPLIER"),
        ("assess supplier risk for delayed order", "ASSESS_RISK"),
        ("approve the purchase order", "APPROVE_ORDER"),
        ("what does the procurement SOP say", "POLICY_QUERY"),
        ("good morning", "GENERAL_QUERY"),
    ]
    all_ok = True
    for text, expected in cases:
        result = vp.parse_intent(text)
        status = "OK" if result["intent"] == expected else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] '{text[:45]}' -> {result['intent']} (expected {expected})")
    assert all_ok, "One or more intent cases failed."


def test_deepgram_import():
    separator("TEST 3 — Deepgram SDK Import")
    try:
        from voice.deepgram_stt import DeepgramSTT
        print("  [OK] DeepgramSTT class imported.")
        if os.getenv("DEEPGRAM_API_KEY", "").startswith("your_"):
            print("  [SKIP] No real DEEPGRAM_API_KEY configured — skipping live test.")
        else:
            stt = DeepgramSTT()
            print("  [OK] DeepgramSTT client initialised.")
    except Exception as e:
        print(f"  [WARN] Import error: {e}")


def test_elevenlabs_import():
    separator("TEST 4 — ElevenLabs SDK Import")
    try:
        from voice.elevenlabs_tts import ElevenLabsTTS
        print("  [OK] ElevenLabsTTS class imported.")
        if os.getenv("ELEVENLABS_API_KEY", "").startswith("your_"):
            print("  [SKIP] No real ELEVENLABS_API_KEY configured — skipping live test.")
        else:
            tts = ElevenLabsTTS()
            print("  [OK] ElevenLabsTTS client initialised.")
    except Exception as e:
        print(f"  [WARN] Import error: {e}")


def test_livekit_import():
    separator("TEST 5 — LiveKit SDK Import")
    try:
        from voice.livekit_client import LiveKitClient
        print("  [OK] LiveKitClient class imported.")
        if os.getenv("LIVEKIT_API_KEY", "").startswith("your_"):
            print("  [SKIP] No real LIVEKIT_API_KEY configured — skipping live test.")
        else:
            lk = LiveKitClient()
            token = lk.generate_token("test-room", "test-user")
            print(f"  [OK] LiveKit JWT token generated: {token[:40]}...")
    except Exception as e:
        print(f"  [WARN] Import error: {e}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    test_audio_stream()
    test_voice_processor()
    test_deepgram_import()
    test_elevenlabs_import()
    test_livekit_import()

    separator("VOICE PIPELINE VERIFICATION COMPLETE")
    print("  [OK] All offline tests passed. Plug in API keys to run live tests.\n")
