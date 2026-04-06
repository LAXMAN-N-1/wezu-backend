import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def alter_table():
    print("Altering 'audit_logs' table to add missing columns...")
    
    commands = [
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS trace_id VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS session_id VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action_id VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS role_prefix VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS level VARCHAR DEFAULT 'INFO'",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS request_method VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS endpoint VARCHAR",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS response_time_ms FLOAT",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS stack_trace TEXT",
        
        # Adding missing indexes if needed
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_trace_id ON audit_logs (trace_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_session_id ON audit_logs (session_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_action_id ON audit_logs (action_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_logs_level ON audit_logs (level)",
    ]
    
    with engine.connect() as conn:
        for cmd in commands:
            try:
                print(f"Executing: {cmd}")
                conn.execute(text(cmd))
                conn.commit()
            except Exception as e:
                print(f"Error executing command: {e}")
                
    print("Table alteration complete.")

if __name__ == "__main__":
    alter_table()
