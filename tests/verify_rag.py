import sys
import os
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.rag_agent import RAGAgent

load_dotenv(override=True)

def run_verification():
    print("Initializing RAG Agent...")
    rag = RAGAgent()

    print("\n--- Test 1: Semantic Product Catalog Search ---")
    query_1 = "marine grade rust proof fasteners"
    print(f"Query: '{query_1}'")
    catalog_results = rag.search_catalog(query_1, limit=2)
    
    for idx, item in enumerate(catalog_results, 1):
        print(f"[{idx}] Match Similarity: {item['similarity']:.4f}")
        print(f"    SKU: {item['sku']}")
        print(f"    Product Name: {item['product_name']}")
        print(f"    Vendor: {item['vendor_name']} (ID: {item['vendor_id']})")
        print(f"    Description: {item['description']}\n")

    print("\n--- Test 2: Semantic Document/Contract Search ---")
    query_2 = "What happens if Steel Dynamics deliveries are late?"
    print(f"Query: '{query_2}'")
    doc_results = rag.search_documents(query_2, limit=1)
    
    for idx, doc in enumerate(doc_results, 1):
        print(f"[{idx}] Match Similarity: {doc['similarity']:.4f}")
        print(f"    Doc Title: {doc['title']}")
        print(f"    Source: {doc['source']}")
        print(f"    Excerpt: {doc['chunk_text']}\n")

    print("--- Test 3: Alternative Steel Supplier Check ---")
    query_3 = "structural load carbon steel sheets"
    print(f"Query: '{query_3}'")
    catalog_results_3 = rag.search_catalog(query_3, limit=2)
    
    for idx, item in enumerate(catalog_results_3, 1):
        print(f"[{idx}] Match Similarity: {item['similarity']:.4f}")
        print(f"    SKU: {item['sku']}")
        print(f"    Product Name: {item['product_name']}")
        print(f"    Vendor: {item['vendor_name']}")
        print(f"    Description: {item['description']}\n")

if __name__ == "__main__":
    run_verification()
