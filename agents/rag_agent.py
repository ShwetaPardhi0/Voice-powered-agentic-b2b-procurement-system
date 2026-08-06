import os
import sys
import json
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection
from rag.retrieve import rag_search
from agents.state import AgentState

load_dotenv(override=True)

# ── Structured Decision Making ───────────────────────────────────────────────

class RAGTaskDecision(BaseModel):
    query: str = Field(description="The natural language search query to run against the RAG vector store.")
    doc_type: str | None = Field(
        description="Optional filter: 'supplier_contract', 'inventory_policy', or 'procurement_sop'."
    )
    supplier_id: str | None = Field(
        description="Optional filter: supplier ID like 'mehta_traders'."
    )


# ── LangGraph RAG Node ───────────────────────────────────────────────────────

def rag_node(state: AgentState) -> dict:
    """
    Worker Node that searches ingested contracts, policies, and SOPs.
    Uses the configured LLM model to formulate the RAG search query and filters
    from supervisor instructions, then calls rag_search().
    """
    context = state.get("context", {})
    instructions = context.get("instructions", "")

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set in environment variables.")

    model_name = os.environ.get("MODEL")
    if not model_name:
        raise RuntimeError("MODEL is not configured in environment variables.")

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.0,
    )

    # Parse query and filters from instructions
    structured_llm = llm.with_structured_output(RAGTaskDecision)
    decision = structured_llm.invoke(f"Instructions: {instructions}")

    # Execute RAG search
    rag_result = rag_search(
        query=decision.query,
        doc_type=decision.doc_type,
        supplier_id=decision.supplier_id,
    )

    context["rag_result"] = rag_result

    # Log action to db agent_logs
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO agent_logs (agent_name, log_level, message) VALUES (%s, %s, %s)",
            ("rag_agent", "INFO", f"RAG search: query='{decision.query}' doc_type={decision.doc_type} supplier_id={decision.supplier_id}")
        )
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[RAG Log Error] {e}")

    msg_content = f"**RAG Agent Response:**\n{rag_result}"

    messages = list(state["messages"]) + [AIMessage(content=msg_content, name="rag_agent")]

    return {
        "messages": messages,
        "next": "supervisor",
        "context": context
    }
