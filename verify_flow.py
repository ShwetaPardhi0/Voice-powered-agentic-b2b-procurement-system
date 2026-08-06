"""
End-to-End RAG Pipeline Verification
Step 1: Initialize DB schema + seed relational data
Step 2: Ingest all 3 sample documents from data/contracts/
Step 3: Run 5 test queries and verify retrieval works
Step 4: Print similarity scores and retrieved chunks
"""

import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(override=True)


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    separator("B2B RAG PIPELINE — END TO END VERIFICATION")

    # -- Step 1: Initialize DB --------------------------------------------
    separator("STEP 1 — Initialize Database Schema & Seed Data")
    from database.init_db import init_db
    init_db()

    # -- Step 2: Ingest Documents -----------------------------------------
    separator("STEP 2 — Ingest Documents from data/contracts/")
    from rag.ingest import ingest_documents
    start = time.time()
    ingest_documents()
    elapsed = time.time() - start
    print(f"\n[TIME]  Ingestion completed in {elapsed:.1f}s")

    # -- Step 3: Verify DB State ------------------------------------------
    separator("STEP 3 — Verify Database State")
    from database.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM rag_documents")
    doc_count = cursor.fetchone()[0]
    print(f"  rag_documents: {doc_count} rows")

    cursor.execute("SELECT COUNT(*) FROM rag_chunks")
    chunk_count = cursor.fetchone()[0]
    print(f"  rag_chunks:    {chunk_count} rows")

    cursor.execute("SELECT COUNT(*) FROM products")
    print(f"  products:      {cursor.fetchone()[0]} rows")

    cursor.execute("SELECT COUNT(*) FROM suppliers")
    print(f"  suppliers:     {cursor.fetchone()[0]} rows")

    cursor.execute("SELECT COUNT(*) FROM inventory")
    print(f"  inventory:     {cursor.fetchone()[0]} rows")

    # Show documents ingested
    cursor.execute("SELECT title, total_chunks FROM rag_documents ORDER BY title")
    rows = cursor.fetchall()
    print("\n  Ingested documents:")
    for title, chunks in rows:
        print(f"    [DOC] {title} — {chunks} chunks")

    cursor.close()
    conn.close()

    # -- Step 4: Run 5 Test Queries ---------------------------------------
    separator("STEP 4 — RAG Retrieval Queries (5 Tests)")
    from rag.retrieve import rag_search

    queries = [
        {
            "label": "TEST 1 — Supplier MOQ (filtered by supplier)",
            "query": "minimum order quantity for steel screws",
            "doc_type": "supplier_contract",
            "supplier_id": "mehta_traders",
        },
        {
            "label": "TEST 2 — Late delivery penalty",
            "query": "What is the penalty for late delivery?",
            "doc_type": "supplier_contract",
            "supplier_id": None,
        },
        {
            "label": "TEST 3 — Reorder point formula (inventory policy)",
            "query": "How is the reorder point calculated? What is the safety stock formula?",
            "doc_type": "inventory_policy",
            "supplier_id": None,
        },
        {
            "label": "TEST 4 — Purchase order approval thresholds",
            "query": "What are the approval thresholds for purchase orders?",
            "doc_type": "procurement_sop",
            "supplier_id": None,
        },
        {
            "label": "TEST 5 — Escalation rules (no filters)",
            "query": "What are the escalation rules when a vendor delays an order?",
            "doc_type": None,
            "supplier_id": None,
        },
    ]

    all_passed = True
    for q in queries:
        print(f"\n{'-'*60}")
        print(f"  {q['label']}")
        print(f"  Query: \"{q['query']}\"")
        filters = []
        if q["doc_type"]:
            filters.append(f"doc_type={q['doc_type']}")
        if q["supplier_id"]:
            filters.append(f"supplier_id={q['supplier_id']}")
        if filters:
            print(f"  Filters: {', '.join(filters)}")
        print(f"{'-'*60}")

        try:
            result = rag_search(
                query=q["query"],
                doc_type=q.get("doc_type"),
                supplier_id=q.get("supplier_id"),
            )
            print(result)

            if "No relevant documents found" in result:
                print("\n  [WARN]  WARNING: No chunks returned!")
                all_passed = False
            else:
                print("\n  [OK] Chunks retrieved successfully")
        except Exception as e:
            print(f"\n  [FAIL] ERROR: {e}")
            all_passed = False

    # -- Summary ----------------------------------------------------------
    separator("VERIFICATION SUMMARY")
    print(f"  Documents ingested: {doc_count}")
    print(f"  Total chunks:       {chunk_count}")
    print(f"  Queries executed:   {len(queries)}")

    if all_passed:
        print("\n  [OK] ALL TESTS PASSED — RAG pipeline is operational")
    else:
        print("\n  [WARN]  SOME TESTS HAD ISSUES — review output above")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
