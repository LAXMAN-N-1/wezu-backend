import os
import sys
import psycopg2

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def debug_psycopg2_direct():
    print("Starting Direct Psycopg2 Debug...")
    
    # Extract params from engine URL
    url = engine.url
    conn_params = {
        "dbname": url.database,
        "user": url.username,
        "password": url.password,
        "host": url.host,
        "port": url.port
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        
        print("Executing direct INSERT...")
        sql = """
        INSERT INTO audit_logs (
            trace_id, action_id, action, timestamp
        ) VALUES (
            'TEST_TRACE_1234567890', 'TEST_ACTION_1234567890', 'TEST_LONG_ACTION_NAME', now()
        )
        """
        
        try:
            cur.execute(sql)
            conn.commit()
            print("SUCCESS: Direct insert worked.")
        except Exception as e:
            print(f"FAILED Direct Insert: {e}")
            conn.rollback()
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    debug_psycopg2_direct()
