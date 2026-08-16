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

from services.slack_service import send_slack_po_approval_request, update_slack_po_message
from services.email_service import send_email_po_approval_request
from services.redis_service import cache_po_state, update_cached_po_status

APPROVAL_THRESHOLD = 25000.00

# ── DB Mutators & Query Helpers ──────────────────────────────────────────────

def create_purchase_order(supplier_id: str, sku: str, quantity: int, price: float) -> dict:
    """
    Creates a new purchase order and line item record.
    If total value exceeds ₹25,000, it marks the PO status as 'PENDING_APPROVAL' in PostgreSQL,
    dispatches Slack Block Kit approval request & Manager Email notification, and caches in Redis.
    Otherwise, marks it as 'APPROVED' (or 'ORDER_PLACED') and updates stock level in PostgreSQL.
    """
    total_val = float(price) * quantity
    po_status = "PENDING_APPROVAL" if total_val > APPROVAL_THRESHOLD else "APPROVED"
    
    conn = get_db_connection()
    conn.autocommit = True
    cursor = conn.cursor()
    
    # 1. Insert Purchase Order in PostgreSQL
    cursor.execute(
        """
        INSERT INTO purchase_orders (supplier_id, status)
        VALUES (%s, %s)
        RETURNING id, status, created_at
        """,
        (supplier_id, po_status)
    )
    po_row = cursor.fetchone()
    po_id, status_db, created_at = po_row
    
    # 2. Insert PO Line Item in PostgreSQL
    cursor.execute(
        """
        INSERT INTO po_line_items (po_id, sku, quantity, price)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (po_id, sku, quantity, Decimal(price))
    )
    li_id = cursor.fetchone()[0]
    
    # 3. If automatically approved (<= ₹25,000), update stock level in PostgreSQL
    if po_status == "APPROVED":
        cursor.execute(
            """
            UPDATE inventory
            SET stock_level = stock_level + %s
            WHERE sku = %s
            """,
            (quantity, sku)
        )
        
    conn.commit()
    cursor.close()
    conn.close()
    
    po_data = {
        "po_id": str(po_id),
        "status": po_status,
        "total_value": total_val,
        "supplier_id": supplier_id,
        "sku": sku,
        "quantity": quantity,
        "unit_price": price,
        "created_at": str(created_at),
        "slack_ts": None,
        "slack_channel": None,
    }

    # 4. If > ₹25,000, trigger Slack Block Kit approval & Manager Email notification
    if po_status == "PENDING_APPROVAL":
        # Send Slack Block Kit approval message
        slack_res = send_slack_po_approval_request(po_data)
        if slack_res.get("success"):
            po_data["slack_ts"] = slack_res.get("ts")
            po_data["slack_channel"] = slack_res.get("channel")

        # Send Manager Email notification
        send_email_po_approval_request(po_data)

    # 5. Cache transient state in Redis
    cache_po_state(str(po_id), po_data)
    
    return po_data


def update_po_status(po_id: str, new_status: str, action_by: str = "Manager") -> dict:
    """
    Updates the status of a purchase order in PostgreSQL (Authoritative Source of Truth).
    On APPROVE: updates PO status to 'APPROVED' and increments stock_level in PostgreSQL.
    On REJECT: updates PO status to 'REJECTED' in PostgreSQL (workflow stops).
    Updates Slack message in place and updates Redis cache.
    """
    new_status = new_status.upper()
    if new_status not in ["APPROVED", "REJECTED"]:
        raise ValueError(f"Invalid status: {new_status}. Must be APPROVED or REJECTED.")

    conn = get_db_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    # 1. Verify PO exists in PostgreSQL
    cursor.execute(
        "SELECT id, supplier_id, status FROM purchase_orders WHERE id::text = %s",
        (str(po_id),)
    )
    po_row = cursor.fetchone()
    if not po_row:
        cursor.close()
        conn.close()
        raise ValueError(f"Purchase order {po_id} not found in database.")

    po_uuid, supplier_id, current_status = po_row

    if current_status in ["APPROVED", "REJECTED"]:
        cursor.close()
        conn.close()
        return {
            "po_id": str(po_id),
            "status": current_status,
            "message": f"PO {po_id} is already in state '{current_status}'.",
        }

    # 2. Fetch Line Items from PostgreSQL
    cursor.execute(
        "SELECT sku, quantity, price FROM po_line_items WHERE po_id::text = %s",
        (str(po_id),)
    )
    items = cursor.fetchall()

    # 3. Update PO status in PostgreSQL
    cursor.execute(
        "UPDATE purchase_orders SET status = %s WHERE id::text = %s",
        (new_status, str(po_id))
    )

    # 4. If APPROVED, increment inventory stock levels in PostgreSQL
    if new_status == "APPROVED":
        for sku, quantity, price in items:
            cursor.execute(
                """
                UPDATE inventory
                SET stock_level = stock_level + %s
                WHERE sku = %s
                """,
                (quantity, sku)
            )

    conn.commit()
    cursor.close()
    conn.close()

    # 5. Update Slack Message in place & update Redis Cache
    from services.redis_service import get_cached_po_state
    cached_data = get_cached_po_state(po_id) or {}
    slack_channel = cached_data.get("slack_channel")
    slack_ts = cached_data.get("slack_ts")

    if slack_channel and slack_ts:
        update_slack_po_message(
            channel_id=slack_channel,
            message_ts=slack_ts,
            po_id=str(po_id),
            status=new_status,
            action_by=action_by,
        )

    update_cached_po_status(str(po_id), new_status)

    return {
        "po_id": str(po_id),
        "status": new_status,
        "supplier_id": supplier_id,
        "action_by": action_by,
        "items": [{"sku": i[0], "quantity": i[1], "price": float(i[2])} for i in items],
    }


def finalize_latest_pending_order() -> dict | None:
    """
    Finds the latest purchase order with status 'PENDING_APPROVAL' 
    and updates it to 'ORDER_PLACED'. Updates stock level as well.
    """
    conn = get_db_connection()
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Get latest pending PO
    cursor.execute(
        """
        SELECT id, supplier_id 
        FROM purchase_orders 
        WHERE status = 'PENDING_APPROVAL' 
        ORDER BY created_at DESC 
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return None
        
    po_id, supplier_id = row
    
    # Update PO status
    cursor.execute(
        "UPDATE purchase_orders SET status = 'ORDER_PLACED' WHERE id = %s",
        (po_id,)
    )
    
    # Fetch line items to update stock levels
    cursor.execute(
        "SELECT sku, quantity, price FROM po_line_items WHERE po_id = %s",
        (po_id,)
    )
    items = cursor.fetchall()
    
    for sku, quantity, price in items:
        cursor.execute(
            """
            UPDATE inventory
            SET stock_level = stock_level + %s
            WHERE sku = %s
            """,
            (quantity, sku)
        )
        
    cursor.close()
    conn.close()
    
    return {
        "po_id": str(po_id),
        "supplier_id": supplier_id,
        "status": "ORDER_PLACED",
        "items": [{"sku": i[0], "quantity": i[1], "price": float(i[2])} for i in items]
    }


# ── Structured Decision Making ───────────────────────────────────────────────

class ProcurementTaskDecision(BaseModel):
    action: str = Field(description="Action to take. Must be 'PLACE_ORDER' or 'APPROVE_PO'.")
    sku: str | None = Field(description="The SKU to order (required for PLACE_ORDER).")
    quantity: int | None = Field(description="The quantity to order (required for PLACE_ORDER).")
    supplier_id: str | None = Field(description="The Supplier ID (required for PLACE_ORDER).")
    price: float | None = Field(description="The unit price contract value of the SKU.")


# ── LangGraph Procurement Node ────────────────────────────────────────────────

def procurement_node(state: AgentState) -> dict:
    """
    Worker Node that registers purchases or processes approvals in the database.
    Uses the configured LLM model to determine execution parameters from instructions.
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
    
    structured_llm = llm.with_structured_output(ProcurementTaskDecision)
    decision = structured_llm.invoke(f"Instructions: {instructions}")
    
    if "po_details" not in context:
        context["po_details"] = []
        
    if decision.action == "APPROVE_PO":
        result = finalize_latest_pending_order()
        if result:
            msg_content = (
                f"**Procurement Agent Response:**\n"
                f"✅ **APPROVED:** Purchase Order {result['po_id']} has been approved and status updated to "
                f"'ORDER_PLACED'. Inventory levels replenished for: "
                f"{', '.join([f'{i[1]} of {i[0]}' for i in result['items']])}."
            )
            context["po_details"].append(result)
            summary = f"Approved pending PO {result['po_id']}."
        else:
            msg_content = "**Procurement Agent Response:**\nNo purchase orders were found pending approval."
            summary = "Checked approvals, none found."
            
    else: # PLACE_ORDER
        # Retrieve missing price from database if required
        sku = decision.sku
        qty = decision.quantity
        supplier = decision.supplier_id
        price = decision.price
        
        if not price:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT price FROM supplier_products WHERE supplier_id = %s AND sku = %s",
                (supplier, sku)
            )
            price_row = cursor.fetchone()
            price = float(price_row[0]) if price_row else 100.00
            cursor.close()
            conn.close()
            
        result = create_purchase_order(supplier, sku, qty, price)
        context["po_details"].append(result)
        
        if result["status"] == "PENDING_APPROVAL":
            msg_content = (
                f"**Procurement Agent Response:**\n"
                f"⚠️ **APPROVAL REQUIRED:** Order value is ₹{result['total_value']:.2f} "
                f"(exceeds threshold of ₹{APPROVAL_THRESHOLD:.2f}).\n"
                f"Purchase Order {result['po_id']} has been created with status 'PENDING_APPROVAL'.\n"
                f"Requires voice authorization to place order."
            )
            summary = f"Created pending PO {result['po_id']}."
        else:
            msg_content = (
                f"**Procurement Agent Response:**\n"
                f"✅ **ORDER PLACED:** Purchase Order {result['po_id']} has been auto-approved and placed "
                f"with supplier '{result['supplier_id']}' for {result['quantity']} units of {result['sku']} "
                f"totaling ₹{result['total_value']:.2f}."
            )
            summary = f"Auto-approved and placed PO {result['po_id']}."

    # Log action to db agent_logs
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO agent_logs (agent_name, log_level, message) VALUES (%s, %s, %s)",
            ("procurement_agent", "INFO", summary)
        )
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Procurement Log Error] {e}")

    messages = list(state["messages"]) + [AIMessage(content=msg_content, name="procurement_agent")]
    
    return {
        "messages": messages,
        "next": "supervisor",
        "context": context
    }
