import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def debug_insert_raw():
    print("Starting Raw SQL Debug Insert...")
    
    # Try inserting a full row manually
    sql = """
    INSERT INTO audit_logs (
        trace_id, session_id, action_id, role_prefix, level, 
        user_id, action, resource_type, details, module, status, timestamp
    ) VALUES (
        'TRACE_123', 'SESS_123', 'ACT_123', 'DLR', 'INFO',
        1, 'TEST_ACTION', 'TEST_RES', 'Test Details', 'system', 'success', now()
    )
    """
    
    with engine.connect() as conn:
        try:
            print("Trying full manual insert...")
            conn.execute(text(sql))
            conn.commit()
            print("SUCCESS: Full insert worked.")
        except Exception as e:
            print(f"FAILED Full Insert: {e}")
            conn.rollback()
            
            # If full fails, try column by column
            cols = [
                "trace_id", "session_id", "action_id", "role_prefix", "level", 
                "user_id", "action", "resource_type", "details", "module", "status"
            ]
            vals = [
                "'TRACE_123'", "'SESS_123'", "'ACT_123'", "'DLR'", "'INFO'",
                "1", "'TEST_ACTION'", "'TEST_RES'", "'Test Details'", "'system'", "'success'"
            ]
            
            print("\nTesting columns individually...")
            for i in range(len(cols)):
                test_col = cols[i]
                test_val = vals[i]
                
                # Check if col is char varying(3) specifically
                test_val_long = "'LONG_VALUE_TEST'" if "id" in test_col or "action" in test_col or "details" in test_col or "module" in test_col else test_val
                if test_col == "role_prefix": test_val_long = "'LONG_PREFIX'"
                
                test_sql = f"INSERT INTO audit_logs ({test_col}, action, timestamp) VALUES ({test_val_long}, 'TEST', now())"
                try:
                    conn.execute(text(test_sql))
                    conn.commit()
                    print(f"  - Column '{test_col}' with long value: OK")
                except Exception as ex:
                    print(f"  - Column '{test_col}' with long value: FAILED! -> {ex}")
                    conn.rollback()

if __name__ == "__main__":
    debug_insert_raw()
