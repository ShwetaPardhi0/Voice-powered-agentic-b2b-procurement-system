"""
voice/livekit_agent.py
----------------------
Production-Grade LiveKit WebRTC AI Voice Agent Worker.

Workflow:
  User Microphone Audio (LiveKit WebRTC Stream)
        │
        ▼
  Deepgram STT (v7.6.0 WebSocket: client.listen.v2.connect)
        │
        ▼
  VoiceProcessor (Intent Parsing) ➔ LangGraph Multi-Agent Supervisor
                                   ➔ Specialist Subagents (Inventory, Supplier, Risk, Forecast, RAG)
        │
        ▼
  ElevenLabs TTS (Speech Synthesis)
        │
        ▼
  LiveKit WebRTC Room Participant (Published Audio Track to User)
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from livekit import rtc
from voice.livekit_client import LiveKitClient
from voice.deepgram_stt import DeepgramSTT
from voice.elevenlabs_tts import ElevenLabsTTS
from agents.voice_processor import VoiceProcessor
from agents.graph import build_graph


class LiveKitVoiceAgent:
    """
    Autonomous LiveKit WebRTC AI Voice Agent for B2B Procurement Control Tower.
    """

    def __init__(self, room_name: str = "procurement-room", identity: str = "Procurement-AI-Agent"):
        self.room_name = room_name
        self.identity = identity
        self.client_token_factory = LiveKitClient()
        self.stt = DeepgramSTT()
        self.tts = ElevenLabsTTS()
        self.processor = VoiceProcessor()
        self.agent_app = build_graph()

        self.room = rtc.Room()
        self._session_history: list = []
        self._is_running = False

    async def start(self):
        """Connects the AI Agent to the LiveKit WebRTC Room and starts event loops."""
        print(f"[LiveKit Agent] Initializing WebRTC worker for room '{self.room_name}'...")
        
        # 1. Generate JWT Token for Agent
        token = self.client_token_factory.generate_token(
            room_name=self.room_name,
            participant_name=self.identity
        )

        # 2. Register Room Event Handlers
        @self.room.on("track_subscribed")
        def on_track_subscribed(track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
            print(f"[LiveKit WebRTC] Subscribed to audio track '{track.sid}' from participant '{participant.identity}'")
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                asyncio.create_task(self._process_audio_track(track, participant))

        @self.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            print(f"[LiveKit WebRTC] Participant '{participant.identity}' joined room.")

        @self.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            print(f"[LiveKit WebRTC] Participant '{participant.identity}' left room.")

        # 3. Connect to LiveKit WebRTC Server
        livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
        await self.room.connect(livekit_url, token)
        self._is_running = True
        print(f"[LiveKit Agent] Connected & listening in LiveKit Room '{self.room_name}'!")

    async def _process_audio_track(self, track: rtc.AudioTrack, participant: rtc.RemoteParticipant):
        """
        Receives continuous WebRTC audio frames from participant microphone stream,
        sends chunks to Deepgram STT, routes to LangGraph Multi-Agent network,
        synthesizes answer via ElevenLabs, and publishes speech audio back to WebRTC room.
        """
        audio_stream = rtc.AudioStream(track)
        audio_buffer = bytearray()

        async for event in audio_stream:
            frame: rtc.AudioFrame = event.frame
            # Append PCM audio frame bytes
            audio_buffer.extend(frame.data.tobytes())

            # Every ~1.5s chunk or buffer size threshold
            if len(audio_buffer) >= 32000:
                chunk = bytes(audio_buffer)
                audio_buffer.clear()
                
                # Transcribe chunk via STT
                transcript = self.stt.transcribe_blob(chunk, mime_type="audio/wav")
                if transcript and len(transcript.strip()) > 3:
                    print(f"\n[LiveKit WebRTC STT] User ({participant.identity}): '{transcript}'")
                    await self._execute_agent_flow(transcript)

    async def _execute_agent_flow(self, transcript: str):
        """
        Runs the transcript through Intent Parsing & LangGraph Multi-Agent network,
        synthesizes ElevenLabs audio, and streams voice reply back.
        """
        # 1. Parse intent
        intent = self.processor.parse_intent(transcript)
        print(f"[LiveKit Agent] Intent Detected: {intent['intent']} | Params: {intent['params']}")

        # 2. Invoke LangGraph multi-agent network
        from langchain_core.messages import HumanMessage, AIMessage
        self._session_history.append(HumanMessage(content=transcript))
        state = {
            "messages": self._session_history,
            "next": "",
            "context": {"intent": intent},
        }

        print("[LiveKit Agent] Running Multi-Agent Graph Execution...")
        final_state = await asyncio.to_thread(self.agent_app.invoke, state)
        self._session_history = list(final_state["messages"])

        # Pick last AI message
        agent_reply = "No response from agent."
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                agent_reply = msg.content
                break

        print(f"[LiveKit Agent Reply]:\n{agent_reply}\n")

        # 3. Synthesize Speech via ElevenLabs TTS
        audio_bytes = await asyncio.to_thread(self.tts.synthesize, agent_reply)
        if audio_bytes:
            print(f"[LiveKit Agent TTS] Generated {len(audio_bytes):,} bytes of speech audio reply.")
            await self._publish_audio_to_room(audio_bytes)

    async def _publish_audio_to_room(self, audio_bytes: bytes):
        """Publishes synthesized AI speech track into the LiveKit WebRTC room."""
        try:
            source = rtc.AudioSource(sample_rate=24000, num_channels=1)
            track = rtc.LocalAudioTrack.create_audio_track("agent-speech", source)
            options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            publication = await self.room.local_participant.publish_track(track, options)
            print(f"[LiveKit WebRTC] Published agent audio track '{publication.sid}' to room!")
        except Exception as e:
            print(f"[LiveKit WebRTC Publish Error]: {e}")

    async def stop(self):
        """Disconnects the AI Agent from the room."""
        if self._is_running:
            await self.room.disconnect()
            self._is_running = False
            print(f"[LiveKit Agent] Disconnected from room '{self.room_name}'.")


if __name__ == "__main__":
    async def run():
        agent = LiveKitVoiceAgent()
        await agent.start()
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await agent.stop()

    asyncio.run(run())
