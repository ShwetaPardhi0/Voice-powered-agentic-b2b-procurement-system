import os
import sys
import json
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection
from agents.state import AgentState

load_dotenv(override=True)

# ── Risk Mapping & Query Helpers ─────────────────────────────────────────────

# Maps our new database supplier IDs to the legacy JSON vendor IDs
SUPPLIER_MAP = {
    "mehta_traders": "V-101",
    "steel_dynamics": "V-102",
    "global_alloys": "V-103",
    "hardware_hub": "V-101", # Assume similar profile to V-101
}

def query_vendor_risk(supplier_id: str) -> dict | None:
    """Reads legacy risk JSON data and maps results to the given supplier_id."""
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "supplier_risk.json"
    )
    if not os.path.exists(data_path):
        return None

    with open(data_path, "r") as f:
        risk_data = json.load(f)

    # Translate DB ID to V-ID
    mapped_id = SUPPLIER_MAP.get(supplier_id, supplier_id)
    return next((item for item in risk_data if item["vendor_id"] == mapped_id), None)


def get_risk_assessment(supplier_id: str) -> dict:
    """Computes a structured grading of the supplier's reliability."""
    risk = query_vendor_risk(supplier_id)
    if not risk:
        return {
            "status": "UNKNOWN",
            "score": 0.5,
            "alerts": [],
            "warning": "No risk profile found for this supplier."
        }

    score = risk["reliability_score"]
    alerts = risk["alerts"]
    
    # Grade risk level
    if score < 0.7 or any(a["severity"] == "HIGH" for a in alerts):
        status = "HIGH_RISK"
    elif score < 0.85 or any(a["severity"] == "MEDIUM" for a in alerts):
        status = "MEDIUM_RISK"
    else:
        status = "SAFE"

    warnings = [a["message"] for a in alerts]
    return {
        "status": status,
        "score": score,
        "alerts": alerts,
        "warning": " | ".join(warnings) if warnings else "No active alerts."
    }


# ── Structured Decision Making ───────────────────────────────────────────────

class RiskTaskDecision(BaseModel):
    supplier_id: str = Field(description="The unique database identifier of the supplier (e.g. 'mehta_traders').")


# ── LangGraph Risk Node ───────────────────────────────────────────────────────

def risk_node(state: AgentState) -> dict:
    """
    Worker Node that evaluates supplier dependability and alerts.
    Uses the configured LLM model to determine the supplier parameter from instructions.
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

    # Decode target supplier
    structured_llm = llm.with_structured_output(RiskTaskDecision)
    decision = structured_llm.invoke(f"Instructions: {instructions}")
    supplier_id = decision.supplier_id

    # Grade supplier
    assessment = get_risk_assessment(supplier_id)

    if "risk_assessments" not in context:
        context["risk_assessments"] = {}

    context["risk_assessments"][supplier_id] = assessment
    summary = f"Assessed risk for '{supplier_id}'. Status: {assessment['status']} | Reliability Score: {assessment['score'] * 100:.1f}%."

    # Log action to db agent_logs
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO agent_logs (agent_name, log_level, message) VALUES (%s, %s, %s)",
            ("risk_agent", "INFO", f"{summary} Warnings: {assessment['warning']}")
        )
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Risk Log Error] {e}")

    # Build agent response message
    if assessment["alerts"]:
        bullets = [
            f"- [{a['type']}] {a['message']} (Severity: {a['severity']})"
            for a in assessment["alerts"]
        ]
        msg_content = (
            f"**Risk Agent Response:**\n{summary}\n"
            f"⚠️ **Active Alerts:**\n" + "\n".join(bullets)
        )
    else:
        msg_content = f"**Risk Agent Response:**\n{summary} No active warnings or alerts on record."

    messages = list(state["messages"]) + [AIMessage(content=msg_content, name="risk_agent")]

    return {
        "messages": messages,
        "next": "supervisor",
        "context": context
    }
