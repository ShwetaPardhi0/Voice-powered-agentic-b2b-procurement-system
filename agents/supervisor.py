import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.state import AgentState

# Load environment configs
load_dotenv(override=True)

# ── Route Struct ──────────────────────────────────────────────────────────────

class RouteResponse(BaseModel):
    next_node: str = Field(
        description="The next node to execute. Must be one of: "
                    "'inventory_agent', 'forecast_agent', 'supplier_agent', "
                    "'risk_agent', 'procurement_agent', 'rag_agent', or '__end__'."
    )
    instructions: str = Field(
        description="Clear instructions for the target agent on what to do next "
                    "(e.g. which SKU to check, what calculation to perform)."
    )


# ── Supervisor Node ───────────────────────────────────────────────────────────

def supervisor_node(state: AgentState) -> dict:
    """
    Decides which sub-agent is responsible for handling the current state of the request.
    Uses the configured LLM model to perform structured classification and routing.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set in environment variables.")

    model_name = os.environ.get("MODEL")
    if not model_name:
        raise RuntimeError("MODEL is not configured in environment variables.")

    # Initialize Gemini model
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.0,
    )

    # Compile the prompt
    system_prompt = (
        "You are the central supervisor orchestrating an Agentic Procurement Control Tower.\n"
        "Your task is to coordinate 6 specialized worker agents based on the user request, "
        "conversation history, and currently generated context. Here is your team:\n\n"
        
        "1. inventory_agent: Queries stock level, warehouse allocations, and reorder thresholds "
        "for products in the 'inventory' and 'products' tables.\n"
        "2. forecast_agent: Estimates next-month demand based on historical sales ('sales_history' table) "
        "and checks if current inventory levels will cause shortages.\n"
        "3. supplier_agent: Pulls supplier list, fetches product pricing/lead times from "
        "'supplier_products' and 'suppliers', and calculates the best quotes for a given quantity.\n"
        "4. risk_agent: Assesses supplier risk/reliability based on supplier details.\n"
        "5. procurement_agent: Creates purchase orders (PO), verifies payment SLA rules against "
        "procurement managers' approval thresholds, and adds items to 'purchase_orders' and 'po_line_items' tables.\n"
        "6. rag_agent: Queries ingested manuals and contracts (Supplier Contract, Inventory Policy, "
        "Procurement SOP) for workflow rules, SLA thresholds, MOQs, and escalation procedures.\n\n"

        "RULES:\n"
        "- If the request requires multiple steps (e.g. checking shortage, then querying supplier, "
        "then checking risk, then placing PO), send to the first agent (inventory_agent or forecast_agent). "
        "Once a sub-agent completes its execution and updates the context, the flow returns to you "
        "so you can route it to the next agent.\n"
        "- If a sub-agent has collected the required details and no further action is needed, "
        "or if the user request is finalized, route to '__end__'.\n"
        "- If you route to an agent, write precise instructions in the 'instructions' field. "
        "Do not output markdown in the JSON structure."
        
        "Tone: Professional, concise, and helpful. Avoid jargon where possible, but use technical terms when necessary."
    )

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])

    # Configure structured extraction
    structured_llm = llm.with_structured_output(RouteResponse)
    response = structured_llm.invoke(messages)

    # Ensure context is initialized inside state
    context = state.get("context", {})
    if not context:
        context = {
            "shortage_items": [],
            "best_quotes": {},
            "risk_assessments": {},
            "po_details": [],
            "rag_result": "",
            "instructions": ""
        }

    # Store supervisor instructions in context for the target worker agent
    context["instructions"] = response.instructions

    print(f"\n[SUPERVISOR] Next Node: {response.next_node}")
    print(f"[SUPERVISOR] Instructions: {response.instructions}")

    return {
        "next": response.next_node,
        "context": context
    }
