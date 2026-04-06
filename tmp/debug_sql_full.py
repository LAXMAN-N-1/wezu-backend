import os
import sys
import logging
from datetime import datetime, UTC
from sqlmodel import Session, select

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine
from app.models.audit_log import AuditLog
from app.utils.audit_context import log_audit_action, trace_ctx, session_ctx, role_prefix_ctx, user_id_ctx

# Force full logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

def debug_sql_full():
    print("Starting Detailed SQL Debug Verification...")
    
    with Session(engine) as db:
        trace_ctx.set("SQL_FULL")
        role_prefix_ctx.set("DLR")
        
        try:
            log_audit_action(
                db=db,
                action="TEST_ACTION",
                module="system",
                details="SQL Full Debug"
            )
            print("Log entity created, committing...")
            db.commit()
            print("SUCCESS")
        except Exception as e:
            # We catch it but SQLAlchemy should have already logged the SQL/Params to stdout
            print(f"\n[CAUGHT ERROR] Type: {type(e)}")
            print(f"[ERROR MESSAGE] {e}")
            db.rollback()

if __name__ == "__main__":
    debug_sql_full()
