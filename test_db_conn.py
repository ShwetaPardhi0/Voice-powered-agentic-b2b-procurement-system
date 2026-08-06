import psycopg2

passwords = ["", "password", "postgres", "admin", "123456"]
connected = False

for pwd in passwords:
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password=pwd,
            dbname="postgres" # default db to check connection
        )
        print(f"Connection Successful! Password: '{pwd}'")
        connected = True
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        print("Postgres Version:", cursor.fetchone()[0])
        
        # Check pgvector availability
        cursor.execute("SELECT * FROM pg_available_extensions WHERE name = 'vector';")
        res = cursor.fetchone()
        if res:
            print("pgvector IS available! Details:", res)
        else:
            print("pgvector is NOT available in the database extensions.")
            
        cursor.close()
        conn.close()
        break
    except Exception as e:
        print(f"Failed with password '{pwd}': {e}")
        
if not connected:
    print("Could not connect to local PostgreSQL instance on port 5432 with tried passwords.")
