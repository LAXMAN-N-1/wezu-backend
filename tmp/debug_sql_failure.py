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

# Enable SQL logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

def debug_sql_failure():
    print("Starting SQL Debug Verification...")
    
    with Session(engine) as db:
        # Set Context
        trace_ctx.set("SQL_DEBUG_TRACE")
        role_prefix_ctx.set("DLR")
        
        print("Executing log_audit_action...")
        try:
            log_audit_action(
                db=db,
                action="TEST_ACTION",
                module="system",
                details="SQL Debug"
            )
            db.commit()
            print("SUCCESS: Log saved.")
        except Exception as e:
            print(f"FAILED: {e}")
            db.rollback()

if __name__ == "__main__":
    debug_sql_failure()
