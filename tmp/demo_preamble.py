import os
import sys
import json
from datetime import datetime, UTC
from sqlmodel import Session, select

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine
from app.models.audit_log import AuditLog, AuditActionType
from app.utils.audit_context import (
    log_audit_action, trace_ctx, session_ctx, role_prefix_ctx, 
    user_id_ctx, generate_trace_id
)
from app.services.audit_service import audit_service

def demonstrate_preamble_format():
    print("=== Preamble Audit Log Format & Sample Case ===")
    
    with Session(engine) as db:
        # 1. SIMULATE MIDDLEWARE START (Request Incoming)
        trace_id = generate_trace_id()
        trace_ctx.set(trace_id)
        session_id = "SESS_DEMO_98765432109876543210" # Mock session from JWT
        session_ctx.set(session_id)
        role_prefix_ctx.set("DLR")
        user_id_ctx.set(101)
        
        print(f"Trace ID Generated: {trace_id}")
        
        # 2. SIMULATE ENDPOINT LOGIC (Bank Account Update)
        print("Executing Endpoint: update_bank_account...")
        
        old_bank_data = {"account_number": "987654321011", "bank": "HDFC"}
        new_bank_data = {"account_number": "112233445566", "bank": "ICICI"}
        
        # This is what happens inside the endpoint
        action_id = log_audit_action(
            db=db,
            action=AuditActionType.DATA_MODIFICATION,
            resource_type="DEALER_BANK",
            target_id=101,
            old_value=old_bank_data,
            new_value=new_bank_data,
            level="CRITICAL",
            details="User updated bank account via Dealer Portal"
        )
        db.commit()
        print(f"Action Logged with Action ID: {action_id}")

        # 3. SIMULATE MIDDLEWARE END (Automatic API Request Logging)
        # This is what happens in AuditMiddleware.dispatch finally block
        metadata = {
            "method": "POST",
            "url": "https://api.wezu.com/v1/dealer/bank-account",
            "status_code": 200,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "headers": {"Authorization": "Bearer masked_token...", "X-Trace-ID": trace_id}
        }
        
        # Normally this is an async task, we call it sync here for the demo
        import asyncio
        async def mock_mw_log():
            await audit_service.log_event(
                event_type="api_request",
                user_id=101,
                resource="/v1/dealer/bank-account",
                action="POST",
                status="success",
                metadata=metadata,
                response_time_ms=45.2
            )
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(mock_mw_log())
        
        # 4. FETCH AND SHOW THE LINKED LOGS
        print("\n=== RESULTING AUDIT LOGS (Linked by Trace ID) ===")
        stmt = select(AuditLog).where(AuditLog.trace_id == trace_id).order_by(AuditLog.timestamp.desc())
        logs = db.exec(stmt).all()
        
        for idx, log in enumerate(logs):
            print(f"\nLOG ENTRY #{idx+1} [{log.level}]")
            print(f"  Field        | Value")
            print(f"  -------------|--------------------------------------")
            print(f"  Action ID    | {log.action_id}")
            print(f"  Trace ID     | {log.trace_id}")
            print(f"  Session ID   | {log.session_id}")
            print(f"  Role Prefix  | {log.role_prefix}")
            print(f"  Action       | {log.action}")
            print(f"  Resource     | {log.resource_type}")
            print(f"  Resp Time    | {log.response_time_ms}ms")
            
            if log.old_value or log.new_value:
                print(f"  Old Value    | {json.dumps(log.old_value)}")
                print(f"  New Value    | {json.dumps(log.new_value)}")
            
            if log.meta_data:
                print(f"  Metadata     | {json.dumps(log.meta_data)[:100]}...")

        # Cleanup
        trace_ctx.set(None)
        session_ctx.set(None)

if __name__ == "__main__":
    demonstrate_preamble_format()
