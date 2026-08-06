"""
RAG Retrieval Function
Embeds query with Gemini text-embedding-004 (task_type: retrieval_query),
runs cosine similarity search on rag_chunks using pgvector <=> operator,
supports filtering by doc_type and supplier_id.
Returns top 3 chunks formatted as a context string.
"""

import os
import sys
import json

from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(override=True)

import google.generativeai as genai

from database.connection import get_db_connection

# ── Config ───────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = "models/text-embedding-004"
TOP_K = 3


def _get_google_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add it to your .env file. "
            "Get one at https://aistudio.google.com/app/apikey"
        )
    return key


def _embed_query(text: str) -> list[float]:
    """Generate 768-dim query embedding using Gemini, falling back to gemini-embedding-2 if not found."""
    genai.configure(api_key=_get_google_api_key())
    try:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type="retrieval_query",
            output_dimensionality=768
        )
        return result["embedding"]
    except Exception as e:
        err_str = str(e).lower()
        if "not found" in err_str or "404" in err_str:
            try:
                result = genai.embed_content(
                    model="models/gemini-embedding-2",
                    content=text,
                    task_type="retrieval_query",
                    output_dimensionality=768
                )
                return result["embedding"]
            except Exception as inner_e:
                raise RuntimeError(f"Gemini query embedding failed: {e} and {inner_e}")
        raise e


# ── Main retrieval function ──────────────────────────────────────────────────

def rag_search(
    query: str,
    doc_type: str = None,
    supplier_id: str = None,
    top_k: int = TOP_K,
) -> str:
    """
    Search rag_chunks for semantically similar content.

    Args:
        query:       Natural language search query.
        doc_type:    Optional filter (e.g. "supplier_contract", "inventory_policy", "procurement_sop").
        supplier_id: Optional filter (e.g. "mehta_traders").
        top_k:       Number of top chunks to return (default 3).

    Returns:
        Formatted context string with the top matching chunks,
        ready to be injected into an LLM prompt.
    """

    # 1. Embed the query
    query_embedding = _embed_query(query)

    # 2. Build SQL with optional metadata filters
    conditions = []
    params = []

    if doc_type:
        conditions.append("c.metadata->>'doc_type' = %s")
        params.append(doc_type)

    if supplier_id:
        conditions.append("c.metadata->>'supplier_id' = %s")
        params.append(supplier_id)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            c.chunk_text,
            c.chunk_index,
            c.metadata,
            d.source,
            d.title,
            c.embedding <=> %s::vector AS distance
        FROM rag_chunks c
        JOIN rag_documents d ON c.document_id = d.id
        {where_clause}
        ORDER BY c.embedding <=> %s::vector ASC
        LIMIT %s
    """

    # Params: embedding (in SELECT for distance), filters, embedding (in ORDER BY), limit
    params = [str(query_embedding)] + params + [str(query_embedding), top_k]

    # 3. Execute
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # 4. Format as context string
    if not rows:
        return "No relevant documents found."

    context_parts = []
    for i, row in enumerate(rows, 1):
        chunk_text, chunk_index, metadata, source, title, distance = row

        # Parse metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        similarity = 1 - distance  # cosine similarity = 1 - cosine distance
        page = metadata.get("page", "N/A")
        doc_type_val = metadata.get("doc_type", "N/A")

        context_parts.append(
            f"[Chunk {i}] source={source} | title={title} | "
            f"page={page} | doc_type={doc_type_val} | "
            f"similarity={similarity:.4f}\n"
            f"{chunk_text}"
        )

    return "\n\n---\n\n".join(context_parts)


# ── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("RAG RETRIEVAL TEST")
    print("=" * 60)

    # Test 1: General query
    print("\n>> Query: 'minimum order quantity for steel screws'")
    result = rag_search("minimum order quantity for steel screws")
    print(result)

    # Test 2: Filtered by doc_type
    print("\n\n>> Query: 'reorder point formula' (doc_type=inventory_policy)")
    result = rag_search("reorder point formula", doc_type="inventory_policy")
    print(result)

    # Test 3: Filtered by supplier_id
    print("\n\n>> Query: 'late delivery penalty' (supplier_id=mehta_traders)")
    result = rag_search("late delivery penalty", supplier_id="mehta_traders")
    print(result)

    # Test 4: Procurement SOP query
    print("\n\n>> Query: 'escalation rules for delayed orders' (doc_type=procurement_sop)")
    result = rag_search("escalation rules for delayed orders", doc_type="procurement_sop")
    print(result)
