import os
import sys
from datetime import datetime, UTC
from sqlmodel import Session, select

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine
from app.models.audit_log import AuditLog, AuditActionType
from app.utils.audit_context import log_audit_action, trace_ctx, session_ctx, role_prefix_ctx, user_id_ctx
from app.utils.data_masking import mask_dict

def test_audit_logging():
    print("Starting Final Audit Logging Verification...")
    
    with Session(engine) as db:
        # 1. Set Context
        trace_ctx.set("TEST_TRACE_ID_123456789012345678")
        session_ctx.set("TEST_SESSION_ID_123456789012345")
        role_prefix_ctx.set("DLR")
        user_id_ctx.set(999)
        
        # 2. Log Action (Simulating sensitive bank update)
        test_new_value = {
            "account_number": "123456789012", # Should be masked
            "bank_name": "Test Bank",
            "ifsc": "SBIN0001234"
        }
        
        test_metadata = {
            "headers": {
                "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", # Should be masked
                "User-Agent": "Mozilla/5.0"
            }
        }
        
        print("Logging CRITICAL audit action...")
        action_id = log_audit_action(
            db=db,
            action=AuditActionType.DATA_MODIFICATION,
            resource_type="DEALER_BANK",
            target_id=1,
            new_value=test_new_value,
            meta_data=test_metadata,
            level="CRITICAL",
            response_time_ms=123.45,
            details="Unit Test: Bank Update Verification"
        )
        db.commit()
        
        print(f"Action Logged with ID prefix: {action_id[:3]}")
        
        # 3. Verify in DB
        stmt = select(AuditLog).where(AuditLog.action_id == action_id)
        log = db.exec(stmt).first()
        
        if not log:
            print("FAILED: Log not found in database!")
            return

        print("--- VERIFICATION RESULTS ---")
        print(f"Trace ID: {log.trace_id} (Expected: TEST_TRACE_...) -> {'PASS' if 'TEST_TRACE' in log.trace_id else 'FAIL'}")
        print(f"Level: {log.level} (Expected: CRITICAL) -> {'PASS' if log.level == 'CRITICAL' else 'FAIL'}")
        print(f"Response Time: {log.response_time_ms}ms (Expected: 123.45) -> {'PASS' if log.response_time_ms == 123.45 else 'FAIL'}")
        
        # Masking verification
        masked_acc = log.new_value.get("account_number")
        print(f"Masked Account: {masked_acc} -> {'PASS' if '***' in str(masked_acc) else 'FAIL'}")
        
        masked_auth = log.meta_data.get("headers", {}).get("Authorization")
        print(f"Masked Auth Header: {masked_auth} -> {'PASS' if '***' in str(masked_auth) else 'FAIL'}")

        # Cleanup Context
        trace_ctx.set(None)
        session_ctx.set(None)
        print("Context Cleared.")
        print("Verification Complete.")

if __name__ == "__main__":
    test_audit_logging()
