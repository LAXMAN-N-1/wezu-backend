import os
import sys
import json
from datetime import datetime, UTC
from sqlmodel import Session, select

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine
from app.models.audit_log import AuditLog
from app.utils.audit_context import log_audit_action, trace_ctx, session_ctx, role_prefix_ctx, user_id_ctx
from app.services.audit_service import audit_service

def test_final_standardization():
    print("Starting Final Audit Standardization Verification...")
    
    with Session(engine) as db:
        # 1. Set Context
        trace_ctx.set("FINAL_TRACE_ID_123456789012345678")
        session_ctx.set("FINAL_SESSION_ID_1234567890123456")
        role_prefix_ctx.set("DLR")
        user_id_ctx.set(99)
        
        # 2. Test Module Validation (Fallback to system)
        print("Test 1: Module Validation (Passing invalid module 'typo_mod')...")
        log_audit_action(
            db=db,
            action="TEST_ACTION",
            module="typo_mod", # Invalid module
            details="Testing module fallback"
        )
        db.commit()
        
        # 3. Test Action Naming Convention (FIN_UPDATE_BANK)
        print("Test 2: Action Naming (Logging FIN_UPDATE_BANK)...")
        action_id_bank = log_audit_action(
            db=db,
            action="FIN_UPDATE_BANK",
            module="finance",
            level="CRITICAL",
            details="Testing standard action code"
        )
        db.commit()
        
        # 4. Verify in DB
        print("\n--- STANDARDIZATION RESULTS ---")
        
        # Check Fallback
        stmt_fallback = select(AuditLog).where(AuditLog.action == "TEST_ACTION")
        log_fallback = db.exec(stmt_fallback).first()
        if log_fallback:
            print(f"Module Fallback: {log_fallback.module} (Expected: system) -> {'PASS' if log_fallback.module == 'system' else 'FAIL'}")
        
        # Check Action Naming
        stmt_bank = select(AuditLog).where(AuditLog.action_id == action_id_bank)
        log_bank = db.exec(stmt_bank).first()
        if log_bank:
            print(f"Action Code: {log_bank.action} (Expected: FIN_UPDATE_BANK) -> {'PASS' if log_bank.action == 'FIN_UPDATE_BANK' else 'FAIL'}")
            print(f"Action ID Prefix: {log_bank.action_id[:3]} (Expected: DLR) -> {'PASS' if log_bank.action_id.startswith('DLR') else 'FAIL'}")

        # Cleanup Context
        trace_ctx.set(None)
        session_ctx.set(None)
        print("Context Cleared.")
        print("Verification Complete.")

if __name__ == "__main__":
    test_final_standardization()
