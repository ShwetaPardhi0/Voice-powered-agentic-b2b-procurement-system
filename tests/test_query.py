import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import get_db_connection

def run_debug():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Simple Join check
    cursor.execute("""
        SELECT p.sku, p.name, v.name 
        FROM product_catalog p 
        JOIN vendors v ON p.vendor_id = v.id;
    """)
    rows = cursor.fetchall()
    print(f"Join returned {len(rows)} matching lines.")
    for r in rows:
        print(f"  SKU={r[0]}, PName={r[1]}, VName={r[2]}")
        
    # 2. Vector distance check with a dummy vector
    import numpy as np
    dummy_vec = np.zeros(1536)
    dummy_vec[0] = 1.0 # standard unit-vector
    dummy_list = dummy_vec.tolist()
    
    print("\nRunning raw similarity check with zero-indexed array...")
    cursor.execute("""
        SELECT p.id, 1 - (p.embedding <=> %s::vector) AS sim
        FROM product_catalog p
        ORDER BY p.embedding <=> %s::vector ASC;
    """, (dummy_list, dummy_list))
    dist_rows = cursor.fetchall()
    print(f"Raw similarity query returned {len(dist_rows)} rows:")
    for dr in dist_rows:
        print(f"  ID={dr[0]}, Similarity={dr[1]}")
        
    cursor.close()
    conn.close()

if __name__ == "__main__":
    run_debug()
