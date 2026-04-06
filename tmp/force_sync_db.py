import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def force_unlimited_varchars():
    print("Forcing all VARCHAR columns in 'audit_logs' to be unlimited...")
    cols = [
        "action", "resource_type", "resource_id", "details", 
        "ip_address", "user_agent", "trace_id", "session_id", 
        "action_id", "role_prefix", "level", "request_method", 
        "endpoint", "module", "status"
    ]
    
    with engine.connect() as conn:
        for col in cols:
            try:
                cmd = f"ALTER TABLE audit_logs ALTER COLUMN {col} TYPE TEXT"
                print(f"Executing: {cmd}")
                conn.execute(text(cmd))
                conn.commit()
            except Exception as e:
                print(f"Error on column {col}: {e}")
                conn.rollback()
    
    print("Force synchronization complete.")

if __name__ == "__main__":
    force_unlimited_varchars()
