"""
chat_agent.py
-------------
Interactive Terminal Interface for the Agentic Procurement Control Tower.

Features:
  - Direct multi-agent text chat via LangGraph network
  - Automated intent recognition (VoiceProcessor)
  - Real-time response streaming from Supervisor & Specialist Agents
  - Optional ElevenLabs TTS audio playback/generation
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from langchain_core.messages import HumanMessage, AIMessage
from agents.voice_processor import VoiceProcessor
from agents.graph import build_graph


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    print("\n" + "=" * 65)
    print("      🎙️  AGENTIC PROCUREMENT CONTROL TOWER — INTERACTIVE CLI  ")
    print("=" * 65)
    print("  Type your queries below (e.g. 'Check shortage for SCR-M8-001')")
    print("  Type 'exit', 'quit', or 'q' to end the session.")
    print("=" * 65 + "\n")

    # Initialize agent graph & voice processor
    print("[Initializing LangGraph Agent Network...]")
    app = build_graph()
    processor = VoiceProcessor()
    session_messages = []
    session_id = "cli_session_1"

    print("\n[OK] Agent Network Ready! Speak or type your request.\n")

    while True:
        try:
            user_input = input("You 👤 > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "q"]:
            print("Session ended. Goodbye!")
            break

        # 1. Parse intent
        intent = processor.parse_intent(user_input)
        print(f"\n[Intent Detected]: {intent['intent']} | Params: {intent['params']}")

        # 2. Invoke multi-agent graph
        session_messages.append(HumanMessage(content=user_input))
        state = {
            "messages": session_messages,
            "next": "",
            "context": {"intent": intent},
        }

        print("[Agentic Control Tower Thinking...]")
        try:
            final_state = app.invoke(state)
            session_messages = list(final_state["messages"])

            # Find last AI message
            agent_reply = "No response from agent."
            for msg in reversed(final_state["messages"]):
                if isinstance(msg, AIMessage) and msg.content:
                    agent_reply = msg.content
                    break

            print(f"\nProcurement Agent 🤖 >\n{agent_reply}\n")
            print("-" * 65 + "\n")

        except Exception as e:
            print(f"\n[Error running agent graph]: {e}\n")


if __name__ == "__main__":
    main()
