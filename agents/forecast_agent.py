import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection
from agents.state import AgentState

load_dotenv(override=True)

# ── DB Query Helpers ─────────────────────────────────────────────────────────

def calculate_forecast(sku: str) -> dict:
    """
    Calculates next month's forecasted demand based on sales_history.
    If no history is found in database, predicts a fallback proportional to the reorder threshold.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query sales history for the SKU in the last 90 days
    sql = """
        SELECT quantity_sold
        FROM sales_history
        WHERE sku = %s
    """
    cursor.execute(sql, (sku,))
    rows = cursor.fetchall()
    
    if rows:
        total_sold = sum(r[0] for r in rows)
        average_qty = total_sold / len(rows)
        # Assume average of 30 days of sales
        predicted_demand = int(average_qty * 30)
        confidence = 0.85
    else:
        # Fallback: Check reorder threshold from inventory
        cursor.execute("SELECT MAX(reorder_threshold) FROM inventory WHERE sku = %s", (sku,))
        val = cursor.fetchone()[0]
        if val is not None and val > 0:
            predicted_demand = int(val * 1.5)
        else:
            predicted_demand = 1000 # Generic fallback
        confidence = 0.50
        
    cursor.close()
    conn.close()
    
    return {
        "sku": sku,
        "forecasted_demand": predicted_demand,
        "confidence": confidence
    }


# ── Structured Decision Making ───────────────────────────────────────────────

class ForecastTaskDecision(BaseModel):
    sku: str = Field(description="The SKU to run demand forecasting on.")


# ── LangGraph Forecast Node ───────────────────────────────────────────────────

def forecast_node(state: AgentState) -> dict:
    """
    Worker Node that predicts next month's demand and flags shortages.
    Uses the configured LLM model to determine SKU parameters from supervisor instructions.
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
    
    # Try to parse the SKU from instructions
    structured_llm = llm.with_structured_output(ForecastTaskDecision)
    decision = structured_llm.invoke(f"Instructions: {instructions}")
    sku = decision.sku
    
    # Generate forecast
    forecast_data = calculate_forecast(sku)
    
    # Check shortages against warehouses
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT i.warehouse_id, i.stock_level, i.reorder_threshold, p.name, p.unit
        FROM inventory i
        JOIN products p ON i.sku = p.sku
        WHERE i.sku = %s
        """,
        (sku,)
    )
    warehouses_stock = cursor.fetchall()
    cursor.close()
    conn.close()
    
    shortages = []
    tot_shortage_amt = 0
    
    for row in warehouses_stock:
        wh_id, stock_level, reorder, p_name, unit = row
        forecasted_demand = forecast_data["forecasted_demand"]
        
        # Will face shortage if stock_level < forecasted_demand or if stock_level <= reorder
        shortage_amount = forecasted_demand - stock_level
        if shortage_amount > 0:
            tot_shortage_amt += shortage_amount
            shortages.append({
                "sku": sku,
                "name": p_name,
                "warehouse_id": wh_id,
                "current_stock": stock_level,
                "reorder_threshold": reorder,
                "forecasted_demand": forecasted_demand,
                "shortage_amount": shortage_amount,
                "unit": unit
            })
            
    # Append shortages to shared state context
    if "shortage_items" not in context:
        context["shortage_items"] = []
    
    # Merge new shortages, avoiding duplicates
    existing_skus_whs = {(item["sku"], item["warehouse_id"]) for item in context["shortage_items"]}
    for s in shortages:
        if (s["sku"], s["warehouse_id"]) not in existing_skus_whs:
            context["shortage_items"].append(s)

    # Log action to db agent_logs
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO agent_logs (agent_name, log_level, message) VALUES (%s, %s, %s)",
            ("forecast_agent", "INFO", f"Generated forecast for {sku}. Shortage found: {tot_shortage_amt} units.")
        )
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Forecast Log Error] {e}")

    # Build agent response message
    if shortages:
        bullets = [
            f"- WH: {s['warehouse_id']} | Current Stock: {s['current_stock']} {s['unit']} | "
            f"Forecasted Demand: {s['forecasted_demand']} {s['unit']} | Shortage: {s['shortage_amount']}"
            for s in shortages
        ]
        msg_content = (
            f"**Forecast Agent Response:**\n"
            f"Analyzed SKU: {sku} ({forecast_data['sku']}). Next month's forecasted demand is "
            f"{forecast_data['forecasted_demand']} units (Confidence: {forecast_data['confidence']:.2f}).\n"
            f"⚠️ **Shortage detected!**\n" + "\n".join(bullets)
        )
    else:
        msg_content = (
            f"**Forecast Agent Response:**\n"
            f"Analyzed SKU: {sku}. Next month's forecasted demand is {forecast_data['forecasted_demand']} units.\n"
            f"No shortage expected. Stock levels are healthy."
        )

    messages = list(state["messages"]) + [AIMessage(content=msg_content, name="forecast_agent")]
    
    return {
        "messages": messages,
        "next": "supervisor",
        "context": context
    }
