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

# ── DB Query Helpers ─────────────────────────────────────────────────────────

def query_stock_levels(sku: str = None) -> list[dict]:
    """Queries inventory levels combined with product details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if sku:
        sql = """
            SELECT i.id, i.sku, p.name, i.warehouse_id, i.stock_level, i.reorder_threshold, p.unit
            FROM inventory i
            JOIN products p ON i.sku = p.sku
            WHERE i.sku = %s
        """
        cursor.execute(sql, (sku,))
    else:
        sql = """
            SELECT i.id, i.sku, p.name, i.warehouse_id, i.stock_level, i.reorder_threshold, p.unit
            FROM inventory i
            JOIN products p ON i.sku = p.sku
            ORDER BY i.sku ASC
        """
        cursor.execute(sql)
        
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return [
        {
            "id": str(r[0]),
            "sku": r[1],
            "name": r[2],
            "warehouse_id": r[3],
            "stock_level": r[4],
            "reorder_threshold": r[5],
            "unit": r[6]
        }
        for r in rows
    ]


def query_low_stock() -> list[dict]:
    """Queries all database inventory rows where stock_level <= reorder_threshold."""
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
        SELECT i.id, i.sku, p.name, i.warehouse_id, i.stock_level, i.reorder_threshold, p.unit
        FROM inventory i
        JOIN products p ON i.sku = p.sku
        WHERE i.stock_level <= i.reorder_threshold
        ORDER BY i.sku ASC
    """
    cursor.execute(sql)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return [
        {
            "id": str(r[0]),
            "sku": r[1],
            "name": r[2],
            "warehouse_id": r[3],
            "stock_level": r[4],
            "reorder_threshold": r[5],
            "unit": r[6]
        }
        for r in rows
    ]


# ── Structured Decision Making ───────────────────────────────────────────────

class InventoryTaskDecision(BaseModel):
    action: str = Field(
        description="Action to execute. Must be: 'CHECK_ALL_STOCK', 'CHECK_SKU_STOCK', or 'CHECK_LOW_STOCK'."
    )
    sku: str | None = Field(
        description="The SKU to check if action is 'CHECK_SKU_STOCK', otherwise null."
    )


# ── LangGraph Inventory Node ──────────────────────────────────────────────────

def inventory_node(state: AgentState) -> dict:
    """
    Worker Node that checks warehouse stock quantities and flags items requiring reordering.
    Uses the configured LLM model to determine DB queries based on supervisor instructions.
    """
    context = state.get("context", {})
    instructions = context.get("instructions", "Check all inventory levels.")
    
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
    
    # Interpret task instructions
    structured_llm = llm.with_structured_output(InventoryTaskDecision)
    decision = structured_llm.invoke(f"Instructions: {instructions}")
    
    # Execute query
    data_found = []
    if decision.action == "CHECK_SKU_STOCK" and decision.sku:
        data_found = query_stock_levels(sku=decision.sku)
        summary = f"Checked stock level for SKU: {decision.sku}."
    elif decision.action == "CHECK_LOW_STOCK":
        data_found = query_low_stock()
        summary = f"Found {len(data_found)} low stock items below reorder thresholds."
        context["shortage_items"] = data_found
    else: # Default is CHECK_ALL_STOCK
        data_found = query_stock_levels()
        summary = f"Checked stock levels across all warehouses ({len(data_found)} records found)."

    # Log action to agent_logs table
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO agent_logs (agent_name, log_level, message) VALUES (%s, %s, %s)",
            ("inventory_agent", "INFO", f"{summary} Results: {json.dumps(data_found)}")
        )
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Inventory Log Error] {e}")

    # Build agent response message
    bullet_points = [
        f"- SKU: {item['sku']} ({item['name']}) | WH: {item['warehouse_id']} | "
        f"Stock: {item['stock_level']} {item['unit']} (Threshold: {item['reorder_threshold']})"
        for item in data_found
    ]
    message_content = f"**Inventory Agent Response:**\n{summary}\n" + "\n".join(bullet_points)
    
    messages = list(state["messages"]) + [AIMessage(content=message_content, name="inventory_agent")]
    
    # Set route back to supervisor
    return {
        "messages": messages,
        "next": "supervisor",
        "context": context
    }
