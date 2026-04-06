import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def debug_update_column_by_column():
    print("Starting Column-by-Column Update Debug...")
    
    with engine.connect() as conn:
        try:
            # 1. Insert empty row (or with minimal info)
            res = conn.execute(text("INSERT INTO audit_logs (action, timestamp) VALUES ('TEST', now()) RETURNING id"))
            log_id = res.fetchone()[0]
            conn.commit()
            print(f"Inserted row with ID: {log_id}")
            
            # 2. Update each column one by one
            cols = {
                "trace_id": "'TRACE_1234567890_LONG'",
                "session_id": "'SESS_1234567890_LONG'",
                "action_id": "'DLR_123456789012345678901234567'",
                "role_prefix": "'DLR_LONG'",
                "level": "'CRITICAL'",
                "module": "'FINANCE_LONG'",
                "status": "'FAILURE_LONG'",
                "resource_type": "'RESOURCE_TYPE_LONG'",
                "details": "'DETAILS_LONG_TEXT_TESTING_TRUNCATION_LIMITS_EXPERIMENTAL'"
            }
            
            for col, val in cols.items():
                print(f"Updating '{col}' with value {val}...")
                try:
                    conn.execute(text(f"UPDATE audit_logs SET {col} = {val} WHERE id = {log_id}"))
                    conn.commit()
                    print(f"  - OK")
                except Exception as ex:
                    print(f"  - FAILED! -> {ex}")
                    conn.rollback()
            
        except Exception as e:
            print(f"Initial setup failed: {e}")
            conn.rollback()

if __name__ == "__main__":
    debug_update_column_by_column()
