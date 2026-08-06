import sys
import os
import traceback

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
import rag.retrieve
from agents.rag_agent import RAGAgent

print(f"Connection properties loaded in connection.py:")
print(f"DB_HOST={DB_HOST}")
print(f"DB_PORT={DB_PORT}")
print(f"DB_NAME={DB_NAME}")
print(f"DB_USER={DB_USER}")

try:
    rag = RAGAgent()
    print("\nRunning RAGAgent search_catalog...")
    res = rag.search_catalog("high structural load steel sheets")
    print("Result size:", len(res))
    print("Result value:", res)
except Exception as e:
    print("\nError inside test:")
    traceback.print_exc()
