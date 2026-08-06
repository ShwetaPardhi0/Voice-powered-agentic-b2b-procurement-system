import os
import sys
import json
from decimal import Decimal
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection
from agents.state import AgentState

load_dotenv(override=True)

# ── DB Query Helpers ─────────────────────────────────────────────────────────

def query_supplier_quotes(sku: str, quantity: int) -> list[dict]:
    """
    Queries supplier_products and suppliers tables for pricing and lead time details.
    Calculates total cost for the specified quantity.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = """
        SELECT sp.supplier_id, s.name, sp.price, sp.lead_time_days
        FROM supplier_products sp
        JOIN suppliers s ON sp.supplier_id = s.id
        WHERE sp.sku = %s
    """
    cursor.execute(sql, (sku,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    quotes = []
    for r in rows:
        supplier_id, name, price, lead_time_days = r
        total_cost = Decimal(price) * quantity
        quotes.append({
            "supplier_id": supplier_id,
            "supplier_name": name,
            "unit_price": float(price),
            "total_cost": float(total_cost),
            "lead_time_days": lead_time_days
        })
        
    # Sort quotes by total cost (primary) and lead time (secondary)
    quotes.sort(key=lambda x: (x["total_cost"], x["lead_time_days"]))
    return quotes


# ── Structured Decision Making ───────────────────────────────────────────────

class SupplierTaskDecision(BaseModel):
    sku: str = Field(description="The SKU to search supplier pricing for.")
    quantity: int = Field(description="The quantity needed to purchase.")


# ── LangGraph Supplier Node ───────────────────────────────────────────────────

def supplier_node(state: AgentState) -> dict:
    """
    Worker Node that queries supplier prices and calculates the best quotes.
    Uses the configured LLM model to determine SKU and quantity parameters from supervisor instructions.
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
    
    # Parse parameters
    structured_llm = llm.with_structured_output(SupplierTaskDecision)
    decision = structured_llm.invoke(f"Instructions: {instructions}")
    sku = decision.sku
    quantity = decision.quantity
    
    # Query quotes
    quotes = query_supplier_quotes(sku, quantity)
    
    if "best_quotes" not in context:
        context["best_quotes"] = {}
        
    if quotes:
        best_quote = quotes[0]
        context["best_quotes"][sku] = best_quote
        summary = f"Found {len(quotes)} suppliers for SKU {sku}. Best supplier is {best_quote['supplier_name']}."
    else:
        summary = f"No quotes found for SKU {sku}."
        best_quote = None

    # Log action to db agent_logs
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        msg = f"Queried quotes for {sku} (qty: {quantity}). Best quote: {best_quote['supplier_id'] if best_quote else 'None'}"
        cursor.execute(
            "INSERT INTO agent_logs (agent_name, log_level, message) VALUES (%s, %s, %s)",
            ("supplier_agent", "INFO", msg)
        )
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Supplier Log Error] {e}")

    # Build agent response message
    if quotes:
        bullets = [
            f"- {q['supplier_name']} ({q['supplier_id']}) | "
            f"Unit Price: ₹{q['unit_price']:.2f} | Total: ₹{q['total_cost']:.2f} | Lead Time: {q['lead_time_days']} days"
            for q in quotes
        ]
        msg_content = (
            f"**Supplier Agent Response:**\n{summary}\n"
            f"Supplier list sorted by pricing:\n" + "\n".join(bullets)
        )
    else:
        msg_content = f"**Supplier Agent Response:**\nNo supplier offers SKU: {sku}."

    messages = list(state["messages"]) + [AIMessage(content=msg_content, name="supplier_agent")]
    
    return {
        "messages": messages,
        "next": "supervisor",
        "context": context
    }
