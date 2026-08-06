"""
RAG Document Ingestion Pipeline
Reads PDF/TXT files from data/contracts/, chunks text, embeds with Gemini
text-embedding-004 (task_type: retrieval_document), and stores in rag_chunks
table via raw SQL.
"""

import os
import sys
import uuid

from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(override=True)

import google.generativeai as genai
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from database.connection import get_db_connection

# -- Embedding ----------------------------------------------------------------

EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIM = 768

def _get_google_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add it to your .env file. "
            "Get one at https://aistudio.google.com/app/apikey"
        )
    return key


def generate_embedding(text: str) -> list[float]:
    """Generate 768-dim embedding using Gemini text-embedding-004, falling back to gemini-embedding-2 if not found."""
    genai.configure(api_key=_get_google_api_key())
    try:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type="retrieval_document",
            output_dimensionality=EMBEDDING_DIM
        )
        return result["embedding"]
    except Exception as e:
        # Check if the error is 404 / NotFound
        err_str = str(e).lower()
        if "not found" in err_str or "404" in err_str:
            # Fall back to gemini-embedding-2 with 768-dim
            try:
                result = genai.embed_content(
                    model="models/gemini-embedding-2",
                    content=text,
                    task_type="retrieval_document",
                    output_dimensionality=768
                )
                return result["embedding"]
            except Exception as inner_e:
                raise RuntimeError(f"Gemini embedding failed with both models: {e} and {inner_e}")
        raise e


# -- Text loading -------------------------------------------------------------

def load_text_from_file(filepath: str) -> list[dict]:
    """Load text from PDF or TXT. Returns list of {text, page} dicts."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        loader = PyPDFLoader(filepath)
        pages = loader.load()
        return [{"text": p.page_content, "page": p.metadata.get("page", 0)} for p in pages]

    elif ext == ".txt":
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return [{"text": content, "page": 0}]

    else:
        print(f"  Skipping unsupported file type: {filepath}")
        return []


# -- Chunking -----------------------------------------------------------------

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _infer_doc_type(filename: str) -> str:
    """Infer doc_type from filename for metadata tagging."""
    name = filename.lower()
    if "contract" in name or "agreement" in name or "sla" in name:
        return "supplier_contract"
    elif "policy" in name or "inventory" in name:
        return "inventory_policy"
    elif "sop" in name or "procurement" in name:
        return "procurement_sop"
    return "general"


def _infer_supplier_id(filename: str, content: str = "") -> str | None:
    """Infer supplier_id from filename or content if possible."""
    name = filename.lower()
    text = content.lower()
    
    if "mehta" in name or "mehta" in text:
        return "mehta_traders"
    if "steel_dynamics" in name or "steel dynamics" in name or "steel dynamics" in text:
        return "steel_dynamics"
    if "global_alloys" in name or "global alloys" in name or "global alloys" in text:
        return "global_alloys"
    return None


# -- Main ingestion -----------------------------------------------------------

def ingest_documents(contracts_dir: str = None):
    """Read all PDF/TXT documents from contracts dir, chunk, embed, store."""

    if contracts_dir is None:
        contracts_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "contracts"
        )

    if not os.path.isdir(contracts_dir):
        raise FileNotFoundError(f"Contracts directory not found: {contracts_dir}")

    files = [
        f for f in os.listdir(contracts_dir)
        if f.endswith((".pdf", ".txt"))
    ]

    if not files:
        print("No PDF/TXT files found in", contracts_dir)
        return

    conn = get_db_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    # Clean previous RAG data
    cursor.execute("DELETE FROM rag_chunks;")
    cursor.execute("DELETE FROM rag_documents;")

    total_chunks = 0

    for filename in sorted(files):
        filepath = os.path.join(contracts_dir, filename)
        print(f"\n[DOC] Processing: {filename}")

        # Generate parent document UUID
        doc_id = uuid.uuid4()
        title = os.path.splitext(filename)[0].replace("_", " ").title()
        doc_type = _infer_doc_type(filename)

        # Load text
        pages = load_text_from_file(filepath)
        if not pages:
            continue

        full_content = " ".join([p["text"] for p in pages])
        supplier_id = _infer_supplier_id(filename, full_content)

        # Chunk all pages
        doc_chunks = []
        for page_info in pages:
            text = page_info["text"].strip()
            if not text:
                continue
            chunks = splitter.split_text(text)
            for chunk in chunks:
                doc_chunks.append({
                    "text": chunk,
                    "page": page_info["page"],
                })

        print(f"   Split into {len(doc_chunks)} chunks")

        # Insert parent document record
        cursor.execute(
            """
            INSERT INTO rag_documents (id, source, title, total_chunks)
            VALUES (%s, %s, %s, %s)
            """,
            (str(doc_id), f"data/contracts/{filename}", title, len(doc_chunks)),
        )

        # Embed and insert chunks
        for idx, chunk_info in enumerate(doc_chunks):
            chunk_text = chunk_info["text"]
            page = chunk_info["page"]

            # Build metadata
            import json
            metadata = {
                "doc_type": doc_type,
                "page": page,
                "chunk_index": idx,
                "word_count": len(chunk_text.split()),
            }
            if supplier_id:
                metadata["supplier_id"] = supplier_id

            # Generate embedding
            embedding = generate_embedding(chunk_text)

            cursor.execute(
                """
                INSERT INTO rag_chunks
                    (document_id, chunk_text, chunk_index, embedding, embedding_model, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(doc_id),
                    chunk_text,
                    idx,
                    embedding,
                    "text-embedding-004",
                    json.dumps(metadata),
                ),
            )

        total_chunks += len(doc_chunks)
        print(f"   [OK] Ingested {len(doc_chunks)} chunks (doc_type={doc_type})")

    cursor.close()
    conn.close()
    print(f"\n{'='*50}")
    print(f"Ingestion complete: {len(files)} files, {total_chunks} total chunks")
    print(f"{'='*50}")


if __name__ == "__main__":
    ingest_documents()
