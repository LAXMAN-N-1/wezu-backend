import os
import sys
import json
from sqlmodel import Session, select

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine
from app.models.audit_log import AuditLog

def show_recent_audits():
    print("--- Fetching Recent Audit Logs from Database ---")
    with Session(engine) as db:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(5)
        logs = db.exec(stmt).all()
        
        if not logs:
            print("No logs found in the 'audit_logs' table.")
            return

        for idx, log in enumerate(logs):
            print(f"\n[ENTRY #{idx+1}] ID: {log.id} | Timestamp: {log.timestamp}")
            print(f"  Action ID : {log.action_id}")
            print(f"  Trace ID  : {log.trace_id}")
            print(f"  Action    : {log.action} ({log.level})")
            print(f"  Resource  : {log.resource_type}")
            print(f"  Details   : {log.details}")
            if log.response_time_ms:
                print(f"  Resp Time : {log.response_time_ms}ms")
            
            # Show a snippet of metadata/values
            if log.meta_data:
                print(f"  Metadata  : {json.dumps(log.meta_data)[:80]}...")
            if log.new_value:
                print(f"  New Value : {json.dumps(log.new_value)[:80]}...")

if __name__ == "__main__":
    show_recent_audits()
