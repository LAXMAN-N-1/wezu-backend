import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def alter_table_v2():
    print("Altering 'audit_logs' table for Advanced Audit Fields (v2)...")
    
    commands = [
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS module VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'success'",
        
        # Optimize with indexes
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_module ON audit_logs (module)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_status ON audit_logs (status)",
    ]
    
    with engine.connect() as conn:
        for cmd in commands:
            try:
                print(f"Executing: {cmd}")
                conn.execute(text(cmd))
                conn.commit()
            except Exception as e:
                print(f"Error executing command: {e}")
                
    print("Table alteration v2 complete.")

if __name__ == "__main__":
    alter_table_v2()
