import sys
import os
import hashlib
import psycopg2
import numpy as np
import traceback

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.connection import get_db_connection

def generate_embedding(text: str) -> list:
    sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    np.random.seed(int(sha[:8], 16))
    vec = np.random.randn(1536)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()

def debug_search():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("DB connected.")
        
        query = "high structural load steel sheets"
        embedding = generate_embedding(query)
        print(f"Embedding generated: first 5 values = {embedding[:5]}")
        print(f"Embedding length: {len(embedding)}")
        
        sql = """
            SELECT 
                p.sku, 
                p.name AS product_name,
                v.name AS vendor_name, 
                1 - (p.embedding <=> %s::vector) AS similarity
            FROM product_catalog p
            JOIN vendors v ON p.vendor_id = v.id
            ORDER BY p.embedding <=> %s::vector ASC
            LIMIT 3;
        """
        
        print("Executing SQL query...")
        cursor.execute(sql, (embedding, embedding))
        rows = cursor.fetchall()
        print(f"Rows returned: {len(rows)}")
        for r in rows:
            print(f"  SKU={r[0]}, Name={r[1]}, Vendor={r[2]}, Similarity={r[3]}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print("\n--- FULL EXCEPTION ---")
        traceback.print_exc()

if __name__ == "__main__":
    debug_search()
