"""
voice/pipeline.py
-----------------
End-to-end voice pipeline:
    Audio bytes ──► Deepgram STT ──► VoiceProcessor (intent parse)
                ──► LangGraph agents ──► ElevenLabs TTS ──► Audio bytes
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage

from voice.deepgram_stt import DeepgramSTT
from voice.elevenlabs_tts import ElevenLabsTTS
from agents.voice_processor import VoiceProcessor
from agents.graph import build_graph


class VoicePipeline:
    """
    Orchestrates the complete voice procurement workflow:
      1. Transcribe audio -> Deepgram STT
      2. Parse intent     -> VoiceProcessor
      3. Run agent graph  -> LangGraph (Supervisor + Specialists)
      4. Synthesise reply -> ElevenLabs TTS
    """

    def __init__(self):
        self.stt = DeepgramSTT()
        self.tts = ElevenLabsTTS()
        self.processor = VoiceProcessor()
        self.agent_app = build_graph()
        # Lightweight in-memory session history
        self._sessions: dict[str, list] = {}

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def run(
        self,
        audio_bytes: bytes,
        session_id: str,
        mime_type: str = "audio/wav",
        tts_output_path: str = None,
    ) -> dict:
        """
        Full synchronous pipeline pass:
          audio_bytes -> transcript -> intent -> agent reply -> tts audio bytes.

        Returns:
            {
              "transcript": str,
              "intent":     dict,
              "response":   str,
              "audio":      bytes  # TTS-synthesised reply
            }
        """
        # 1. Transcribe --------------------------------------------------
        transcript = self.stt.transcribe_blob(audio_bytes, mime_type=mime_type)
        print(f"[Pipeline] Transcript: {transcript!r}")

        if not transcript:
            return {
                "transcript": "",
                "intent": {"intent": "UNKNOWN", "params": {}},
                "response": "Sorry, I couldn't understand the audio.",
                "audio": None,
            }

        # 2. Parse intent ------------------------------------------------
        intent = self.processor.parse_intent(transcript)
        print(f"[Pipeline] Intent: {intent}")

        # 3. Run LangGraph agent network --------------------------------
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        self._sessions[session_id].append(HumanMessage(content=transcript))
        state = {
            "messages": self._sessions[session_id],
            "next": "",
            "context": {"intent": intent},
        }
        final_state = self.agent_app.invoke(state)
        self._sessions[session_id] = list(final_state["messages"])

        # Pick last AI message
        agent_reply = "No response from agent."
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                agent_reply = msg.content
                break
        print(f"[Pipeline] Agent reply: {agent_reply[:120]}...")

        # 4. Synthesise TTS reply ----------------------------------------
        audio_bytes_out = self.tts.synthesize(agent_reply, output_path=tts_output_path)
        print(f"[Pipeline] TTS generated {len(audio_bytes_out):,} bytes.")

        return {
            "transcript": transcript,
            "intent": intent,
            "response": agent_reply,
            "audio": audio_bytes_out,
        }
