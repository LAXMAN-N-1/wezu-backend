import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def check_atttypmod():
    print("Checking raw atttypmod for 'audit_logs'...")
    query = """
    SELECT attname, atttypmod
    FROM pg_attribute
    WHERE attrelid = 'audit_logs'::regclass
    AND attnum > 0
    AND NOT attisdropped;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        for row in result:
            print(f"- {row[0]}: {row[1]}")

if __name__ == "__main__":
    check_atttypmod()
