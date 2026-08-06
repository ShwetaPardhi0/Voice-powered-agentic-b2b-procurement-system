import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "procurement_ai")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")

def print_paths():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname="postgres", # standard maintenance DB
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        cursor.execute("SELECT version();")
        print("PG Version:", cursor.fetchone()[0])
        
        cursor.execute("SHOW data_directory;")
        print("Data Directory:", cursor.fetchone()[0])
        
        cursor.execute("SELECT name, setting FROM pg_settings WHERE name IN ('data_directory', 'hba_file', 'config_file');")
        for row in cursor.fetchall():
            print(f"{row[0]}: {row[1]}")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error querying settings: {e}")

if __name__ == "__main__":
    print_paths()
