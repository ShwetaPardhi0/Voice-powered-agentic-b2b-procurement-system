"""
services/reminder_service.py
----------------------------
Automated PO Reminder & Escalation Engine.

Lifecycle Schedule:
  - Day 0 : Initial notification (sent upon PO creation)
  - Day 1 : Day 1 Reminder notification (Slack + Email)
  - Day 2 : Day 2 Final Reminder notification (Slack + Email)
  - Day 3 : Escalate & mark PO status as OVERDUE in PostgreSQL

CRITICAL RULES:
  1. STOP ALL REMINDERS IMMEDIATELY if PO status is APPROVED or REJECTED.
  2. OVERDUE status must NEVER update inventory or count as approval.
  3. PostgreSQL remains the single authoritative source of truth; Redis stores transient stage counters.
"""

import os
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from database.connection import get_db_connection
from services.slack_service import send_slack_po_reminder, update_slack_po_message
from services.email_service import send_email_po_approval_request
from services.redis_service import is_redis_available, redis_client

load_dotenv(override=True)


def get_po_reminder_stage(po_id: str) -> int:
    """Returns current reminder stage from Redis (default 0)."""
    if not is_redis_available():
        return 0
    try:
        val = redis_client.get(f"po:{po_id}:reminder_stage")
        return int(val) if val is not None else 0
    except Exception:
        return 0


def set_po_reminder_stage(po_id: str, stage: int):
    """Sets current reminder stage in Redis cache."""
    if not is_redis_available():
        return
    try:
        redis_client.set(f"po:{po_id}:reminder_stage", str(stage))
    except Exception as e:
        print(f"[Reminder Service Error] Failed to set stage in Redis: {e}")


def process_pending_po_reminders(simulated_days_offset: float = 0.0) -> list[dict]:
    """
    Scans all 'PENDING_APPROVAL' purchase orders in PostgreSQL.
    Evaluates elapsed age + simulated_days_offset and dispatches Day 1, Day 2, or Day 3 Escalations.

    Returns list of action summaries.
    """
    conn = get_db_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    # Query all PENDING_APPROVAL POs directly from PostgreSQL (Authoritative Source of Truth)
    cursor.execute(
        """
        SELECT po.id, po.supplier_id, po.status, po.created_at,
               pli.sku, pli.quantity, pli.price
        FROM purchase_orders po
        LEFT JOIN po_line_items pli ON pli.po_id = po.id
        WHERE po.status = 'PENDING_APPROVAL'
        ORDER BY po.created_at ASC
        """
    )
    rows = cursor.fetchall()

    now_utc = datetime.now(timezone.utc)
    results = []

    for row in rows:
        po_id_raw, supplier_id, status, created_at, sku, quantity, price = row
        po_id = str(po_id_raw)

        # ── RULE 1: Stop all reminders immediately if PO is APPROVED or REJECTED
        if status in ["APPROVED", "REJECTED"]:
            print(f"[Reminder Service] PO {po_id} is in terminal state '{status}'. Skipping reminders.")
            continue

        now_local = datetime.now()
        created_at_naive = created_at.replace(tzinfo=None) if hasattr(created_at, 'tzinfo') and created_at.tzinfo else created_at
        age_seconds = (now_local - created_at_naive).total_seconds()
        age_days = (age_seconds / 86400.0) + simulated_days_offset

        total_value = float(price) * quantity if price and quantity else 0.0
        po_data = {
            "po_id": po_id,
            "supplier_id": supplier_id,
            "sku": sku or "N/A",
            "quantity": quantity or 0,
            "unit_price": float(price) if price else 0.0,
            "total_value": total_value,
            "status": status,
            "risk_level": "Medium",
        }

        current_stage = get_po_reminder_stage(po_id)

        # ── DAY 3 ESCALATION & OVERDUE
        if age_days >= 3.0 and current_stage < 3:
            # Mark OVERDUE in PostgreSQL
            cursor.execute(
                "UPDATE purchase_orders SET status = 'OVERDUE' WHERE id::text = %s",
                (po_id,)
            )
            conn.commit()

            # ── RULE 2: OVERDUE must NEVER update inventory or count as approval!

            # Send Escalation Slack Card & Email
            stage_title = "🚨 DAY 3 ESCALATION — PO OVERDUE"
            send_slack_po_reminder(po_data, stage_title)

            # Update existing Slack card if cached
            from services.redis_service import get_cached_po_state
            cached = get_cached_po_state(po_id) or {}
            slack_ch, slack_ts = cached.get("slack_channel"), cached.get("slack_ts")
            if slack_ch and slack_ts:
                update_slack_po_message(slack_ch, slack_ts, po_id, "OVERDUE", action_by="System Escalation")

            send_email_po_approval_request({
                **po_data,
                "status": "OVERDUE",
            })

            set_po_reminder_stage(po_id, 3)
            summary = f"PO {po_id} (age {age_days:.1f}d): Escalated to OVERDUE in PostgreSQL. Stock level unchanged."
            results.append({"po_id": po_id, "action": "ESCALATED_OVERDUE", "summary": summary})
            print(f"[Reminder Service] {summary}")

        # ── DAY 2 FINAL REMINDER
        elif age_days >= 2.0 and current_stage < 2:
            stage_title = "⏰ DAY 2 FINAL REMINDER"
            send_slack_po_reminder(po_data, stage_title)
            send_email_po_approval_request(po_data)
            set_po_reminder_stage(po_id, 2)
            summary = f"PO {po_id} (age {age_days:.1f}d): Sent Day 2 Final Reminder."
            results.append({"po_id": po_id, "action": "REMINDER_DAY_2", "summary": summary})
            print(f"[Reminder Service] {summary}")

        # ── DAY 1 REMINDER
        elif age_days >= 1.0 and current_stage < 1:
            stage_title = "⏰ DAY 1 REMINDER"
            send_slack_po_reminder(po_data, stage_title)
            send_email_po_approval_request(po_data)
            set_po_reminder_stage(po_id, 1)
            summary = f"PO {po_id} (age {age_days:.1f}d): Sent Day 1 Reminder."
            results.append({"po_id": po_id, "action": "REMINDER_DAY_1", "summary": summary})
            print(f"[Reminder Service] {summary}")

    cursor.close()
    conn.close()
    return results
