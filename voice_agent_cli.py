"""
voice_agent_cli.py
------------------
Interactive Terminal CLI for Voice-to-Voice AI Procurement System.

Simulates the voice pipeline pass:
  Audio Input / Text Voice Command ──► Deepgram STT ──► VoiceProcessor Intent
                                  ──► LangGraph Multi-Agent ──► ElevenLabs TTS
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from voice.pipeline import VoicePipeline


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    print("\n" + "=" * 65)
    print("      🎙️  VOICE-TO-VOICE AI PROCUREMENT ASSISTANT CLI  ")
    print("=" * 65)
    print("  This CLI processes voice inputs / speech text through the complete")
    print("  Deepgram STT ➔ LangGraph Agent ➔ ElevenLabs TTS pipeline.")
    print("  Output audio will be saved to 'response.mp3' for playback.")
    print("=" * 65 + "\n")

    pipeline = VoicePipeline()
    session_id = "voice_cli_session_1"

    while True:
        try:
            print("\nOptions:")
            print("  1. Speak / Type prompt (Generates ElevenLabs TTS Voice Response)")
            print("  2. Process audio file (e.g. sample.wav)")
            print("  3. Exit")
            choice = input("\nSelect [1-3] > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting voice CLI. Goodbye!")
            break

        if choice == "3" or choice.lower() in ["exit", "quit", "q"]:
            print("Session ended. Goodbye!")
            break

        if choice == "1":
            text_input = input("Enter speech text > ").strip()
            if not text_input:
                continue

            print("\n[Running Voice Pipeline...]")
            output_audio_path = os.path.abspath("response.mp3")
            result = pipeline.run(
                audio_bytes_or_transcript=text_input,
                session_id=session_id,
                tts_output_path=output_audio_path,
            )

            print(f"\n[Transcript]:     {result.get('transcript')}")
            print(f"[Parsed Intent]:  {result.get('intent')}")
            print(f"[Agent Response]: {result.get('response')}\n")

            if result.get("audio"):
                print(f"🔊 Synthesised Voice Response saved to: {output_audio_path}")
                print("  (Open response.mp3 to hear the AI voice reply!)")
            else:
                print("[Note]: TTS audio not generated (Check ELEVENLABS_API_KEY in .env)")

        elif choice == "2":
            file_path = input("Enter path to audio file > ").strip()
            if not os.path.exists(file_path):
                print(f"[Error]: File not found at '{file_path}'")
                continue

            with open(file_path, "rb") as f:
                audio_bytes = f.read()

            output_audio_path = os.path.abspath("response.mp3")
            print("\n[Processing Audio File through STT & Multi-Agent Network...]")
            result = pipeline.run(
                audio_bytes_or_transcript=audio_bytes,
                session_id=session_id,
                tts_output_path=output_audio_path,
            )

            print(f"\n[Transcript]:     {result.get('transcript')}")
            print(f"[Parsed Intent]:  {result.get('intent')}")
            print(f"[Agent Response]: {result.get('response')}\n")

            if result.get("audio"):
                print(f"🔊 Synthesised Voice Response saved to: {output_audio_path}")
            else:
                print("[Note]: TTS audio not generated (Check ELEVENLABS_API_KEY in .env)")


if __name__ == "__main__":
    main()
