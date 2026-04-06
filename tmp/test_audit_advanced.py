import os
import sys
from datetime import datetime, UTC
from sqlmodel import Session, select

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine
from app.models.audit_log import AuditLog
from app.utils.audit_context import log_audit_action, trace_ctx, session_ctx, role_prefix_ctx, user_id_ctx
from app.services.audit_service import audit_service

def test_advanced_audit():
    print("Starting Advanced Audit Design Verification...")
    
    with Session(engine) as db:
        # 1. Set Context
        trace_ctx.set("ADV_TRACE_ID_123456789012345678")
        session_ctx.set("ADV_SESSION_ID_12345678901234567")
        role_prefix_ctx.set("DLR")
        user_id_ctx.set(101)
        
        # 2. Log Action (Simulating specialized action code and module)
        print("Logging ADVANCED audit action (FIN_UPD_BANK in finance module)...")
        action_id = log_audit_action(
            db=db,
            action="FIN_UPD_BANK",
            module="finance",
            status="success",
            resource_type="DEALER_BANK",
            target_id=1,
            new_value={"account": "masked_acc"},
            level="CRITICAL",
            response_time_ms=88.8,
            details="Unit Test: Advanced Audit Verification"
        )
        db.commit()
        
        # 3. Simulate Middleware Failure Case
        import asyncio
        async def mock_failure_mw():
             await audit_service.log_event(
                event_type="api_request",
                user_id=101,
                resource="/v1/dealer/bank-account",
                action="POST",
                status="failure",
                metadata={"error": "Test failure"},
                response_time_ms=150.0,
                module="api"
            )
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(mock_failure_mw())
        
        print("--- VERIFICATION RESULTS ---")
        
        # Verify specific fields in the first log
        stmt = select(AuditLog).where(AuditLog.action_id == action_id)
        log1 = db.exec(stmt).first()
        
        if log1:
            print(f"Log 1 - Action: {log1.action} (Expected: FIN_UPD_BANK) -> {'PASS' if log1.action == 'FIN_UPD_BANK' else 'FAIL'}")
            print(f"Log 1 - Module: {log1.module} (Expected: finance) -> {'PASS' if log1.module == 'finance' else 'FAIL'}")
            print(f"Log 1 - Status: {log1.status} (Expected: success) -> {'PASS' if log1.status == 'success' else 'FAIL'}")
        else:
            print("FAILED: Log 1 not found!")

        # Verify specific fields in the middleware failure log
        # Order by timestamp to get the most recent for this trace
        stmt_failed = select(AuditLog).where(AuditLog.status == "failure").order_by(AuditLog.timestamp.desc())
        log2 = db.exec(stmt_failed).first()
        
        if log2:
            print(f"Log 2 - Level: {log2.level} (Expected: INFO/WARNING/ERROR) -> Log Level is {log2.level}")
            print(f"Log 2 - Status: {log2.status} (Expected: failure) -> {'PASS' if log2.status == 'failure' else 'FAIL'}")
            print(f"Log 2 - Module: {log2.module} (Expected: api) -> {'PASS' if log2.module == 'api' else 'FAIL'}")
        else:
            print("FAILED: Log 2 (failure) not found!")

        # Cleanup Context
        trace_ctx.set(None)
        session_ctx.set(None)
        print("Context Cleared.")
        print("Verification Complete.")

if __name__ == "__main__":
    test_advanced_audit()
