import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import get_db_connection

def check_rows():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for table in ["inventory", "vendors", "product_catalog", "documents"]:
            cursor.execute(f"SELECT count(*) FROM {table};")
            print(f"Table '{table}' has {cursor.fetchone()[0]} rows.")
            
        cursor.execute("SELECT id, sku, name, vendor_id, (embedding IS NULL) as emb_null FROM product_catalog;")
        print("\nProducts in catalog:")
        for r in cursor.fetchall():
            print(f"ID={r[0]}, SKU={r[1]}, Name={r[2]}, Vendor={r[3]}, Embedding Null={r[4]}")
            
        cursor.execute("SELECT id, source, title, chunk_index, (embedding IS NULL) as emb_null FROM documents;")
        print("\nDocuments in table:")
        for r in cursor.fetchall():
            print(f"ID={r[0]}, Source={r[1]}, Title={r[2]}, Index={r[3]}, Embedding Null={r[4]}")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error checking rows: {e}")

if __name__ == "__main__":
    check_rows()
