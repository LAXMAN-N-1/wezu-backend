import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def alter_table_v3():
    print("Altering 'audit_logs' table for Optimization (v3)...")
    
    # Partial index for 'failure' status for high-speed error analysis
    commands = [
        "CREATE INDEX IF NOT EXISTS idx_audit_failure ON audit_logs(status) WHERE status = 'failure';"
    ]
    
    with engine.connect() as conn:
        for cmd in commands:
            try:
                print(f"Executing: {cmd}")
                conn.execute(text(cmd))
                conn.commit()
            except Exception as e:
                print(f"Error executing command: {e}")
                
    print("Table alteration v3 complete.")

if __name__ == "__main__":
    alter_table_v3()
