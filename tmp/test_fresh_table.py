import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def test_on_fresh_table():
    print("Testing on a fresh copy of the table structure...")
    
    # 1. Create a clone table
    sql_create = """
    CREATE TABLE IF NOT EXISTS audit_logs_temp (
        id SERIAL PRIMARY KEY,
        trace_id VARCHAR,
        session_id VARCHAR,
        action_id VARCHAR,
        role_prefix VARCHAR,
        level VARCHAR,
        user_id INTEGER,
        action VARCHAR,
        resource_type VARCHAR,
        details VARCHAR,
        module VARCHAR,
        status VARCHAR,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT now()
    )
    """
    
    with engine.connect() as conn:
        try:
            print("Creating 'audit_logs_temp'...")
            conn.execute(text(sql_create))
            conn.commit()
            
            print("Trying to insert long values into 'audit_logs_temp'...")
            sql_insert = """
            INSERT INTO audit_logs_temp (action, role_prefix, module, status)
            VALUES ('LONG_ACTION_NAME_TEST', 'LONG_PREFIX', 'LONG_MODULE', 'LONG_STATUS')
            """
            conn.execute(text(sql_insert))
            conn.commit()
            print("SUCCESS: Long values inserted into FRESH table.")
            
            # 2. Cleanup
            # conn.execute(text("DROP TABLE audit_logs_temp"))
            # conn.commit()
            
        except Exception as e:
            print(f"FAILED on fresh table: {e}")
            conn.rollback()

if __name__ == "__main__":
    test_on_fresh_table()
