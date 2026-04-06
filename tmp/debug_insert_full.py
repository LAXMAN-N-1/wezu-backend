import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def debug_insert_full_strings():
    print("Starting Detailed Raw SQL Debug (Full Strings)...")
    
    # 32-char strings
    t_id = "TRACE_12345678901234567890123456"
    s_id = "SESS_123456789012345678901234567"
    a_id = "DLR_123456789012345678901234567" # 32 chars
    
    sql = f"""
    INSERT INTO audit_logs (
        trace_id, session_id, action_id, role_prefix, level, 
        user_id, action, resource_type, details, module, status, timestamp
    ) VALUES (
        '{t_id}', '{s_id}', '{a_id}', 'DLR', 'INFO',
        1, 'TEST_ACTION', 'TEST_RES', 'Test Details', 'system', 'success', now()
    )
    """
    
    with engine.connect() as conn:
        try:
            print("Trying manual insert with 32-char strings...")
            conn.execute(text(sql))
            conn.commit()
            print("SUCCESS: Full insert worked with 32-char strings.")
        except Exception as e:
            print(f"FAILED: {e}")
            conn.rollback()

if __name__ == "__main__":
    debug_insert_full_strings()
