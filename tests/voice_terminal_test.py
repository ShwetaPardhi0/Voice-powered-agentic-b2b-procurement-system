"""
voice_terminal_test.py
──────────────────────
Direct voice terminal — speak and get response. No menus.
"""

import os
import sys
import io
import wave
import numpy as np
import soundfile as sf
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voice.pipeline import VoicePipeline

import sounddevice as sd

SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.01
SILENCE_DURATION = 1.5   # seconds of silence before stopping


def record_until_silence() -> bytes:
    """Record mic until silence detected — no fixed duration."""
    print("\n🎙️  Listening... (speak now)\n")

    chunk_size = int(SAMPLE_RATE * 0.1)  # 100ms chunks
    silence_chunks_needed = int(SILENCE_DURATION / 0.1)

    recorded = []
    silent_count = 0
    speaking_started = False

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        while True:
            chunk, _ = stream.read(chunk_size)
            recorded.append(chunk.copy())

            volume = np.abs(chunk).mean()

            if volume > SILENCE_THRESHOLD:
                speaking_started = True
                silent_count = 0
                print("█", end="", flush=True)
            else:
                if speaking_started:
                    silent_count += 1
                    print("░", end="", flush=True)

            # Stop after silence post-speech
            if speaking_started and silent_count >= silence_chunks_needed:
                print("\n\n✅ Got it! Processing...\n")
                break

    # Convert to WAV bytes
    audio_np = np.concatenate(recorded, axis=0)
    audio_int16 = (audio_np * 32767).astype(np.int16)

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())

    return wav_io.getvalue()


def play_audio_file(file_path: str):
    audio_data, sample_rate = sf.read(file_path)
    sd.play(audio_data, sample_rate)
    sd.wait()               # blocks until speech finishes, THEN listens again


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    print("\n" + "=" * 55)
    print("   🎙️  VOICE PROCUREMENT ASSISTANT — speak to start")
    print("=" * 55)
    print("   Ctrl+C to exit\n")

    pipeline = VoicePipeline()
    session_id = "terminal_session"
    output_audio_path = os.path.abspath("response.wav")
    

    print("[OK] Pipeline Ready! Listening...\n")

    while True:
        try:
            # Immediately listen — no menu, no prompts
            audio_bytes = record_until_silence()

            result = pipeline.run(
                audio_bytes=audio_bytes,
                session_id=session_id,
                mime_type="audio/wav",
                tts_output_path=output_audio_path,
            )

            print(f"📝 You said    : {result.get('transcript')!r}")
            print(f"🤖 Agent reply : {result.get('response')}\n")

            if result.get("audio"):
                print(f"🔊 Playing response...\n")
                play_audio_file(output_audio_path)

            print("-" * 55)

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break


if __name__ == "__main__":
    main()
