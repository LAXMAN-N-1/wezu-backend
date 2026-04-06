import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine
from app.models.audit_log import AuditLog
from sqlmodel import SQLModel

def reconstruct_audit_table():
    print("RECONSTRUCTING 'audit_logs' table to clear ghost constraints...")
    
    with engine.connect() as conn:
        try:
            # 1. Drop existing table
            print("Dropping existing table...")
            conn.execute(text("DROP TABLE IF EXISTS audit_logs CASCADE"))
            conn.commit()
            
            # 2. Recreate using SQLModel (the source of truth)
            print("Recreating table from SQLModel definition...")
            AuditLog.__table__.create(engine)
            
            print("RECONSTRUCTION SUCCESSFUL.")
            
            # 3. Add the partial index from V3 too
            print("Adding standardized optimization indexes...")
            commands = [
                "CREATE INDEX IF NOT EXISTS idx_audit_failure ON audit_logs(status) WHERE status = 'failure';"
            ]
            for cmd in commands:
                conn.execute(text(cmd))
                conn.commit()
            print("V3 Indexes re-added.")
                
        except Exception as e:
            print(f"RECONSTRUCTION FAILED: {e}")
            conn.rollback()

if __name__ == "__main__":
    reconstruct_audit_table()
