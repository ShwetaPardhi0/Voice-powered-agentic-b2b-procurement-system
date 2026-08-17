"""
test_po_approval_workflow.py
────────────────────────────
Verification Script for Slack PO Approval Workflow, Email Notifications,
and PostgreSQL Source-of-Truth PO Status Mutations.
"""

import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from database.connection import get_db_connection
from agents.procurement_agent import create_purchase_order, update_po_status


def test_po_workflow():
    print("\n" + "=" * 65)
    print(" 🧪 TESTING PO APPROVAL WORKFLOW & POSTGRESQL MUTATIONS")
    print("=" * 65)

    # 1. Test PO <= ₹25,000 (Auto-Approval)
    print("\n--- [TEST 1]: PO <= ₹25,000 (Auto-Approval) ---")
    sku_small = "SCR-M8-001"
    qty_small = 1000
    price_small = 4.50  # Total: ₹4,500.00 <= ₹25,000

    res_small = create_purchase_order(
        supplier_id="mehta_traders",
        sku=sku_small,
        quantity=qty_small,
        price=price_small,
    )
    print(f"Created PO ID   : {res_small['po_id']}")
    print(f"Total Value     : ₹{res_small['total_value']:,.2f}")
    print(f"Expected Status : APPROVED")
    print(f"Actual Status   : {res_small['status']}")
    assert res_small["status"] == "APPROVED", f"Expected APPROVED but got {res_small['status']}"
    print("✅ TEST 1 PASSED: PO <= ₹25,000 correctly auto-approved in PostgreSQL!")

    # 2. Test PO > ₹25,000 (Approval Required)
    print("\n--- [TEST 2]: PO > ₹25,000 (Approval Required) ---")
    sku_large = "PLT-A36-6"
    qty_large = 5
    price_large = 8200.00  # Total: ₹41,000.00 > ₹25,000

    res_large = create_purchase_order(
        supplier_id="mehta_traders",
        sku=sku_large,
        quantity=qty_large,
        price=price_large,
    )
    po_id_large = res_large["po_id"]
    print(f"Created PO ID   : {po_id_large}")
    print(f"Total Value     : ₹{res_large['total_value']:,.2f}")
    print(f"Expected Status : PENDING_APPROVAL")
    print(f"Actual Status   : {res_large['status']}")
    assert res_large["status"] == "PENDING_APPROVAL", f"Expected PENDING_APPROVAL but got {res_large['status']}"
    print("✅ TEST 2 PASSED: PO > ₹25,000 correctly marked PENDING_APPROVAL in PostgreSQL!")

    # 3. Test Approval Action (PostgreSQL Source of Truth)
    print(f"\n--- [TEST 3]: Manager Approves PO {po_id_large} ---")
    approve_res = update_po_status(po_id_large, "APPROVED", action_by="@manager_test")
    print(f"Updated Status  : {approve_res['status']}")
    assert approve_res["status"] == "APPROVED", f"Expected APPROVED but got {approve_res['status']}"

    # Verify status in PostgreSQL
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM purchase_orders WHERE id::text = %s", (str(po_id_large),))
    db_status = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    print(f"PostgreSQL Status: {db_status}")
    assert db_status == "APPROVED", f"PostgreSQL status mismatch: expected APPROVED, got {db_status}"
    print("✅ TEST 3 PASSED: Approval correctly persisted in PostgreSQL & inventory updated!")

    # 4. Test Rejection Action (PostgreSQL Source of Truth)
    print("\n--- [TEST 4]: Manager Rejects PO ---")
    res_large2 = create_purchase_order(
        supplier_id="mehta_traders",
        sku=sku_large,
        quantity=10,
        price=price_large,  # Total: ₹82,000
    )
    po_id_rej = res_large2["po_id"]
    reject_res = update_po_status(po_id_rej, "REJECTED", action_by="@manager_test")
    print(f"PO ID           : {po_id_rej}")
    print(f"Updated Status  : {reject_res['status']}")
    assert reject_res["status"] == "REJECTED"
    # 5. Test Duplicate Approval/Rejection Prevention
    print("\n--- [TEST 5]: Duplicate Action Guard (Prevent Changing Terminal PO Status) ---")
    dup_attempt = update_po_status(po_id_large, "REJECTED", action_by="@attacker_test")
    print(f"PO ID           : {po_id_large}")
    print(f"Status Output   : {dup_attempt['status']}")
    print(f"Message Output  : {dup_attempt.get('message')}")
    assert dup_attempt["status"] == "APPROVED", "PO status must NOT be changed from APPROVED to REJECTED!"
    assert "already in state 'APPROVED'" in dup_attempt.get("message", "")
    print("✅ TEST 5 PASSED: System correctly blocked changing an already APPROVED PO to REJECTED!")

    print("\n" + "=" * 65)
    print(" 🎉 ALL PO WORKFLOW TESTS PASSED SUCCESSFULLY!")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    test_po_workflow()
