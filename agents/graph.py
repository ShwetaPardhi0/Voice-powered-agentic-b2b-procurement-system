"""
LangGraph Multi-Agent Orchestration Graph with Parallel & Sequential Execution.
Independent worker agents run concurrently using asyncio / ThreadPool,
while dependent steps execute sequentially.
"""

import os
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor

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

# ── Node Identifiers ──────────────────────────────────────────────────────────

SUPERVISOR = "supervisor"
PARALLEL_NODE = "parallel_executor"
INVENTORY = "inventory_agent"
FORECAST = "forecast_agent"
SUPPLIER = "supplier_agent"
RISK = "risk_agent"
PROCUREMENT = "procurement_agent"
RAG = "rag_agent"

WORKER_MAP = {
    INVENTORY: inventory_node,
    FORECAST: forecast_node,
    SUPPLIER: supplier_node,
    RISK: risk_node,
    PROCUREMENT: procurement_node,
    RAG: rag_node,
}

WORKER_NODES = list(WORKER_MAP.keys())


# ── Parallel Executor Node ─────────────────────────────────────────────────────

def parallel_executor_node(state: AgentState) -> dict:
    """
    Executes multiple independent worker agents concurrently in parallel threads,
    combining their context outputs into the state.
    """
    context = state.get("context", {})
    parallel_targets = context.get("parallel_nodes", [])

    if not parallel_targets:
        return {"next": SUPERVISOR, "context": context}

    print(f"\n⚡ [PARALLEL EXECUTOR] Running {len(parallel_targets)} agents concurrently: {parallel_targets}")

    merged_context = dict(context)
    new_messages = []

    def execute_worker(target_name: str):
        worker_fn = WORKER_MAP.get(target_name)
        if not worker_fn:
            return {}
        try:
            res = worker_fn(state)
            return res
        except Exception as err:
            print(f"[PARALLEL EXECUTOR ERROR in {target_name}]: {err}")
            return {}

    with ThreadPoolExecutor(max_workers=len(parallel_targets)) as executor:
        futures = [executor.submit(execute_worker, target) for target in parallel_targets]
        results = [f.result() for f in futures]

    for res in results:
        if "context" in res and isinstance(res["context"], dict):
            for k, v in res["context"].items():
                if v:  # Merge non-empty context keys
                    merged_context[k] = v
        if "messages" in res and res["messages"]:
            new_messages.extend(res["messages"])

    # Clear parallel queue once executed
    merged_context["parallel_nodes"] = []

    return {
        "next": SUPERVISOR,
        "context": merged_context,
        "messages": new_messages
    }


# ── Routing Decision ───────────────────────────────────────────────────────────

def route_next(state: AgentState) -> str:
    """
    Reads state['next'] set by supervisor:
    - 'parallel': routes to parallel_executor_node
    - worker node name: routes directly to sequential worker
    - '__end__': terminates graph execution
    """
    next_node = state.get("next", "__end__")
    if next_node == "parallel":
        return PARALLEL_NODE
    if next_node == "__end__":
        return END
    return next_node


# ── Graph Assembly ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Assembles the multi-agent graph supporting parallel & sequential workflows.
    """
    graph = StateGraph(AgentState)

    # Add Supervisor & Parallel Executor
    graph.add_node(SUPERVISOR, supervisor_node)
    graph.add_node(PARALLEL_NODE, parallel_executor_node)

    # Add worker nodes
    for name, fn in WORKER_MAP.items():
        graph.add_node(name, fn)

    graph.set_entry_point(SUPERVISOR)

    # Conditional Routing from Supervisor
    edge_map = {name: name for name in WORKER_NODES}
    edge_map[PARALLEL_NODE] = PARALLEL_NODE
    edge_map[END] = END

    graph.add_conditional_edges(
        SUPERVISOR,
        route_next,
        edge_map
    )

    # Parallel Executor and Workers return to Supervisor
    graph.add_edge(PARALLEL_NODE, SUPERVISOR)
    for worker in WORKER_NODES:
        graph.add_edge(worker, SUPERVISOR)

    return graph.compile()


# ── Utility Runner ────────────────────────────────────────────────────────────

def run_agent(user_message: str) -> str:
    """Convenience single-prompt execution runner."""
    from langchain_core.messages import HumanMessage
    app = build_graph()
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "next": "",
        "context": {}
    }
    final_state = app.invoke(initial_state)

    for msg in reversed(final_state.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            return msg.content
    return "No response generated."


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    from dotenv import load_dotenv
    load_dotenv(override=True)

    print("=" * 60)
    print(" 🚀 TESTING PARALLEL & SEQUENTIAL MULTI-AGENT GRAPH")
    print("=" * 60)

    query = "Check inventory for PLT-A36-6 and pull SLA terms from supplier contract simultaneously."
    print(f"\nUSER QUERY: {query}\n")
    output = run_agent(query)
    print(f"\nFINAL AGENT RESPONSE:\n{output}")
