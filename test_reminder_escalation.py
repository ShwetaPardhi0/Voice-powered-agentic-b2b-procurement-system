"""
test_reminder_escalation.py
────────────────────────────
Verification Script for 4-Stage PO Reminder & Escalation Lifecycle:
  1. Day 0: Initial Notification
  2. Day 1: Reminder Notification
  3. Day 2: Final Reminder Notification
  4. Day 3: Escalation to OVERDUE in PostgreSQL (Inventory MUST NOT change)
  5. Immediate Stop Rule: Reminders stop when PO is APPROVED or REJECTED
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from database.connection import get_db_connection
from agents.procurement_agent import create_purchase_order, update_po_status
from services.reminder_service import process_pending_po_reminders, set_po_reminder_stage


def test_reminder_system():
    print("\n" + "=" * 70)
    print(" 🧪 TESTING PO REMINDER & ESCALATION SYSTEM (DAYS 0 -> 1 -> 2 -> 3)")
    print("=" * 70)

    # 1. Create a PO requiring approval (> ₹25,000)
    print("\n--- [STEP 1]: Create PO > ₹25,000 (Day 0 Initial Notification) ---")
    sku = "PLT-A36-6"
    qty = 5
    price = 8200.00  # ₹41,000

    # Record initial stock level in PostgreSQL
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT stock_level FROM inventory WHERE sku = %s", (sku,))
    initial_stock = c.fetchone()[0]
    c.close()
    conn.close()

    res = create_purchase_order(
        supplier_id="mehta_traders",
        sku=sku,
        quantity=qty,
        price=price,
    )
    po_id = res["po_id"]
    print(f"Created PO ID    : {po_id}")
    print(f"Initial Status   : {res['status']}")
    print(f"Initial Stock    : {initial_stock}")
    assert res["status"] == "PENDING_APPROVAL"
    set_po_reminder_stage(po_id, 0)
    print("✅ STEP 1 PASSED: PO created with status PENDING_APPROVAL!")

    # 2. Simulate Day 1 Reminder
    print("\n--- [STEP 2]: Simulate Day 1 (Age = 1.1 Days) ---")
    act_d1 = process_pending_po_reminders(simulated_days_offset=1.1)
    d1_item = next((a for a in act_d1 if a["po_id"] == po_id), None)
    print(f"Day 1 Action     : {d1_item}")
    assert d1_item is not None and d1_item["action"] == "REMINDER_DAY_1"
    print("✅ STEP 2 PASSED: Day 1 Reminder successfully dispatched!")

    # 3. Simulate Day 2 Final Reminder
    print("\n--- [STEP 3]: Simulate Day 2 (Age = 2.1 Days) ---")
    act_d2 = process_pending_po_reminders(simulated_days_offset=2.1)
    d2_item = next((a for a in act_d2 if a["po_id"] == po_id), None)
    print(f"Day 2 Action     : {d2_item}")
    assert d2_item is not None and d2_item["action"] == "REMINDER_DAY_2"
    print("✅ STEP 3 PASSED: Day 2 Final Reminder successfully dispatched!")

    # 4. Simulate Day 3 Escalation & OVERDUE
    print("\n--- [STEP 4]: Simulate Day 3 (Age = 3.1 Days -> OVERDUE Safeguard Check) ---")
    act_d3 = process_pending_po_reminders(simulated_days_offset=3.1)
    d3_item = next((a for a in act_d3 if a["po_id"] == po_id), None)
    print(f"Day 3 Action     : {d3_item}")
    assert d3_item is not None and d3_item["action"] == "ESCALATED_OVERDUE"

    # Verify PostgreSQL Status is OVERDUE
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT status FROM purchase_orders WHERE id::text = %s", (po_id,))
    db_status = c.fetchone()[0]

    c.execute("SELECT stock_level FROM inventory WHERE sku = %s", (sku,))
    final_stock = c.fetchone()[0]
    c.close()
    conn.close()

    print(f"PostgreSQL Status: {db_status}")
    print(f"Inventory Stock  : {final_stock} (Initial: {initial_stock})")

    assert db_status == "OVERDUE", f"Expected OVERDUE in PostgreSQL, got {db_status}"
    assert final_stock == initial_stock, "CRITICAL SAFEGUARD FAILED: Stock level must NOT change when PO is OVERDUE!"
    print("✅ STEP 4 PASSED: PO marked OVERDUE in PostgreSQL and inventory stock level remained UNCHANGED!")

    # 5. Test Immediate Stop Rule (Terminal PO Status)
    print("\n--- [STEP 5]: Immediate Stop Rule (No reminders for APPROVED/REJECTED POs) ---")
    # Create another PO and approve it
    res_app = create_purchase_order(supplier_id="mehta_traders", sku=sku, quantity=qty, price=price)
    po_app_id = res_app["po_id"]
    update_po_status(po_app_id, "APPROVED", action_by="@manager")

    act_stop = process_pending_po_reminders(simulated_days_offset=5.0)
    app_in_act = any(a["po_id"] == po_app_id for a in act_stop)
    print(f"Approved PO in active reminders list? : {app_in_act}")
    assert not app_in_act, "CRITICAL RULE FAILED: Reminders must stop immediately for APPROVED/REJECTED POs!"
    print("✅ STEP 5 PASSED: Approved/Rejected POs immediately ignored by reminder engine!")

    print("\n" + "=" * 70)
    print(" 🎉 ALL PO REMINDER & ESCALATION TESTS PASSED PERFECTLY!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_reminder_system()
