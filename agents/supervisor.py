import os
import sys
from datetime import datetime
from typing import List
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.state import AgentState

load_dotenv(override=True)

# ── Structured Route Response ─────────────────────────────────────
class RouteResponse(BaseModel):
    next_node: str = Field(
        default="parallel",
        description="Set to 'parallel' if multiple independent agents "
                    "should run concurrently. Otherwise set to a single "
                    "target node name: 'inventory_agent', 'forecast_agent',"
                    "'supplier_agent', 'risk_agent', 'procurement_agent', "
                    "'rag_agent', or '__end__'."
    )
    parallel_nodes: List[str] = Field(
        default_factory=list,
        description="If next_node is 'parallel', list 2 or more independent "
                    "agent names to execute concurrently."
    )
    instructions: str = Field(
        description="Clear instructions for the target agent(s) on what "
                    "parameters or checks to execute."
    )


# ── Live Context Builder ──────────────────────────────────────────
def build_live_context(state: AgentState) -> str:
    """Inject live DB snapshot into supervisor context."""
    try:
        from database.connection import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Critical shortages
        cursor.execute("""
            SELECT p.name, i.quantity_in_stock, i.reorder_point
            FROM inventory i
            JOIN products p ON i.product_id = p.id
            WHERE i.quantity_in_stock <= i.reorder_point
            LIMIT 5
        """)
        shortages = cursor.fetchall()
        shortage_text = "\n".join([
            f"  ⚠️  {row[0]}: {row[1]} units (reorder at {row[2]})"
            for row in shortages
        ]) or "  ✅ No critical shortages"

        # Pending POs
        cursor.execute("""
            SELECT id, supplier_id, status, total_amount
            FROM purchase_orders
            WHERE status = 'pending'
            LIMIT 5
        """)
        pos = cursor.fetchall()
        po_text = "\n".join([
            f"  📋 PO#{row[0]}: Supplier {row[1]} | ${row[3]} | {row[2]}"
            for row in pos
        ]) or "  ✅ No pending POs"

        cursor.close()
        conn.close()

        return f"""
LIVE SYSTEM SNAPSHOT ({datetime.now().strftime('%Y-%m-%d %H:%M')}):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL SHORTAGES:
{shortage_text}

PENDING PURCHASE ORDERS:
{po_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    except Exception as e:
        return f"[Live context unavailable: {e}]"


# ── Supervisor Node ───────────────────────────────────────────────
def supervisor_node(state: AgentState) -> dict:
    """
    Central Supervisor Orchestrator.
    Determines whether independent worker agents can run concurrently
    (parallel) or sequentially when output dependencies exist.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    model_name = os.environ.get("MODEL", "gemini-2.5-flash")

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.0,
    )

    # ── Build live context ────────────────────────────────────────
    live_context = build_live_context(state)  # ← NOW ACTUALLY CALLED

    system_prompt = (
        "You are the central supervisor orchestrating an Agentic "
        "Procurement Control Tower.\n"
        "Your goal is to choose the fastest and most accurate execution "
        "plan using 6 specialized worker agents:\n\n"
        "1. inventory_agent: Queries stock levels, warehouse allocations, "
        "reorder points.\n"
        "2. forecast_agent: Estimates next-month sales demand and shortage "
        "risks.\n"
        "3. supplier_agent: Pulls supplier product pricing, lead times, and "
        "calculates best quotes.\n"
        "4. risk_agent: Assesses supplier reliability, risk metrics, and "
        "compliance.\n"
        "5. procurement_agent: Creates purchase orders (PO), checks payment "
        "SLAs & approval thresholds.\n"
        "6. rag_agent: Queries contract PDFs, SLA policies, MOQs, and "
        "escalation rules.\n\n"
        "OPTIMIZATION RULES:\n"
        "- PARALLEL EXECUTION: If a user request requires checking "
        "independent information, set next_node='parallel' and list all "
        "independent agents in 'parallel_nodes'.\n"
        "- SEQUENTIAL DEPENDENCY: If an agent requires output from a "
        "previous agent, do NOT include it in parallel_nodes. Run prep "
        "agents first, then route sequentially.\n"
        "- GREETINGS / SIMPLE QUESTIONS: Set next_node='__end__', "
        "write a helpful answer in instructions.\n"
        "- WORK COMPLETE: When context has all required answers, "
        "set next_node='__end__'.\n\n"
        f"{live_context}"  # ← LIVE DB CONTEXT INJECTED HERE
    )

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    structured_llm = llm.with_structured_output(RouteResponse)
    response = structured_llm.invoke(messages)

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

    context["instructions"] = response.instructions
    context["parallel_nodes"] = (
        response.parallel_nodes
        if response.next_node == "parallel"
        else []
    )

    print(f"\n[SUPERVISOR] Next Node: {response.next_node} | "
          f"Parallel: {response.parallel_nodes}")
    print(f"[SUPERVISOR] Instructions: {response.instructions}")
    print(f"[SUPERVISOR] Live Context injected: ✅")  # confirm it ran

    return {
        "next": response.next_node,
        "context": context,
        "messages": state["messages"] + [AIMessage(content=response.instructions)]
    }
























# import os
# import sys
# from typing import List, Optional
# from dotenv import load_dotenv
# from langchain_core.messages import SystemMessage, AIMessage
# from langchain_google_genai import ChatGoogleGenerativeAI
# from pydantic import BaseModel, Field

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from agents.state import AgentState

# load_dotenv(override=True)

# # ── Structured Route Response ──────────────────────────────────────────────────

# class RouteResponse(BaseModel):
#     next_node: str = Field(
#         default="parallel",
#         description="Set to 'parallel' if multiple independent agents should run concurrently. "
#                     "Otherwise set to a single target node name: "
#                     "'inventory_agent', 'forecast_agent', 'supplier_agent', "
#                     "'risk_agent', 'procurement_agent', 'rag_agent', or '__end__'."
#     )
#     parallel_nodes: List[str] = Field(
#         default_factory=list,
#         description="If next_node is 'parallel', list 2 or more independent agent names to execute concurrently "
#                     "(e.g. ['inventory_agent', 'supplier_agent', 'rag_agent'])."
#     )
#     instructions: str = Field(
#         description="Clear instructions for the target agent(s) on what parameters or checks to execute."
#     )



# # ── Supervisor Node ───────────────────────────────────────────────────────────

# def supervisor_node(state: AgentState) -> dict:
#     """
#     Central Supervisor Orchestrator.
#     Determines whether independent worker agents can run concurrently (parallel)
#     or sequentially when output dependencies exist.
#     """
#     api_key = os.environ.get("GOOGLE_API_KEY")
#     if not api_key:
#         raise RuntimeError("GOOGLE_API_KEY is not set in environment variables.")

#     model_name = os.environ.get("MODEL", "gemini-2.5-flash")

#     llm = ChatGoogleGenerativeAI(
#         model=model_name,
#         google_api_key=api_key,
#         temperature=0.0,
#     )

#     system_prompt = (
#         "You are the central supervisor orchestrating an Agentic Procurement Control Tower.\n"
#         "Your goal is to choose the fastest and most accurate execution plan using 6 specialized worker agents:\n\n"
#         "1. inventory_agent: Queries stock levels, warehouse allocations, reorder points.\n"
#         "2. forecast_agent: Estimates next-month sales demand and shortage risks.\n"
#         "3. supplier_agent: Pulls supplier product pricing, lead times, and calculates best quotes.\n"
#         "4. risk_agent: Assesses supplier reliability, risk metrics, and compliance.\n"
#         "5. procurement_agent: Creates purchase orders (PO), checks payment SLAs & approval thresholds.\n"
#         "6. rag_agent: Queries contract PDFs, SLA policies, MOQs, and escalation rules.\n\n"
#         "OPTIMIZATION RULES:\n"
#         "- PARALLEL EXECUTION: If a user request requires checking independent information (e.g. checking stock AND supplier prices AND contract SLAs), "
#         "set next_node='parallel' and list all independent agents in 'parallel_nodes'. They will run concurrently!\n"
#         "- SEQUENTIAL DEPENDENCY: If an agent requires output from a previous agent (e.g. procurement_agent creating a PO needs supplier quotes & stock shortage first), "
#         "do NOT include procurement_agent in parallel_nodes. First run the prep agents in parallel, then route to procurement_agent sequentially.\n"
#         "- GREETINGS / SIMPLE QUESTIONS: Set next_node='__end__', write answer in instructions.\n"
#         "- WORK COMPLETE: When context has all required answers, set next_node='__end__'.\n"
#     )

#     messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
#     structured_llm = llm.with_structured_output(RouteResponse)
#     response = structured_llm.invoke(messages)

#     context = state.get("context", {})
#     if not context:
#         context = {
#             "shortage_items": [],
#             "best_quotes": {},
#             "risk_assessments": {},
#             "po_details": [],
#             "rag_result": "",
#             "instructions": ""
#         }

#     context["instructions"] = response.instructions
#     context["parallel_nodes"] = response.parallel_nodes if response.next_node == "parallel" else []

#     print(f"\n[SUPERVISOR] Next Node: {response.next_node} | Parallel Targets: {response.parallel_nodes}")
#     print(f"[SUPERVISOR] Instructions: {response.instructions}")

#     return {
#         "next": response.next_node,
#         "context": context,
#         "messages": state["messages"] + [AIMessage(content=response.instructions)]
#     }
