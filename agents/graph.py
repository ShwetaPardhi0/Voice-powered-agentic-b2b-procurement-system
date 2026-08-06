"""
LangGraph Multi-Agent Orchestration Graph
Assembles the supervisor + 6 worker nodes into a cyclic StateGraph.
The supervisor routes tasks to the appropriate worker, and workers
return control to the supervisor after completing their step.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END

from agents.state import AgentState
from agents.supervisor import supervisor_node
from agents.inventory_agent import inventory_node
from agents.forecast_agent import forecast_node
from agents.supplier_agent import supplier_node
from agents.risk_agent import risk_node
from agents.procurement_agent import procurement_node
from agents.rag_agent import rag_node

# ── Node Names ────────────────────────────────────────────────────────────────

SUPERVISOR = "supervisor"
INVENTORY = "inventory_agent"
FORECAST = "forecast_agent"
SUPPLIER = "supplier_agent"
RISK = "risk_agent"
PROCUREMENT = "procurement_agent"
RAG = "rag_agent"

WORKER_NODES = [INVENTORY, FORECAST, SUPPLIER, RISK, PROCUREMENT, RAG]

# ── Routing Function ──────────────────────────────────────────────────────────

def route_next(state: AgentState) -> str:
    """
    Reads state['next'] set by the supervisor or worker nodes
    and returns the name of the next node to execute.
    """
    next_node = state.get("next", "__end__")
    if next_node == "__end__":
        return END
    return next_node


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Builds and compiles the LangGraph multi-agent graph.
    
    Flow:
        START -> supervisor -> (conditional) -> worker_node -> supervisor -> ... -> END
    
    The supervisor decides which worker to call. Each worker executes its task,
    updates the state, and routes back to the supervisor. The supervisor then
    decides the next step or ends the conversation.
    """
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node(SUPERVISOR, supervisor_node)
    graph.add_node(INVENTORY, inventory_node)
    graph.add_node(FORECAST, forecast_node)
    graph.add_node(SUPPLIER, supplier_node)
    graph.add_node(RISK, risk_node)
    graph.add_node(PROCUREMENT, procurement_node)
    graph.add_node(RAG, rag_node)

    # Entry point: always start at supervisor
    graph.set_entry_point(SUPERVISOR)

    # Supervisor routes to a worker or END
    graph.add_conditional_edges(
        SUPERVISOR,
        route_next,
        {
            INVENTORY: INVENTORY,
            FORECAST: FORECAST,
            SUPPLIER: SUPPLIER,
            RISK: RISK,
            PROCUREMENT: PROCUREMENT,
            RAG: RAG,
            END: END,
        }
    )

    # Every worker returns to supervisor
    for worker in WORKER_NODES:
        graph.add_edge(worker, SUPERVISOR)

    return graph.compile()


# ── Convenience Runner ────────────────────────────────────────────────────────

def run_agent(user_message: str) -> str:
    """
    Convenience function to run a single user message through the multi-agent graph.
    Returns the final AI response as a string.
    """
    from langchain_core.messages import HumanMessage

    app = build_graph()

    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "next": "",
        "context": {}
    }

    final_state = app.invoke(initial_state)

    # Extract the last AI message as the response
    messages = final_state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content:
            return msg.content

    return "No response generated."


# ── CLI Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    from dotenv import load_dotenv
    load_dotenv(override=True)

    print("=" * 60)
    print("  B2B PROCUREMENT CONTROL TOWER - Multi-Agent Test")
    print("=" * 60)

    test_queries = [
        "Check current stock levels for all products across warehouses.",
        "What is the SLA penalty for late delivery from Mehta Traders?",
        "Will we face shortages next month?",
    ]

    for query in test_queries:
        print(f"\n{'─' * 60}")
        print(f"USER: {query}")
        print(f"{'─' * 60}")
        response = run_agent(query)
        print(f"\nFINAL RESPONSE:\n{response}")
