import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def check_triggers():
    print("Checking for triggers on 'audit_logs'...")
    query = """
    SELECT
        tgname AS trigger_name
    FROM
        pg_trigger
    WHERE
        tgrelid = 'audit_logs'::regclass
        AND tgisinternal = false;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        found = False
        for row in result:
            print(f"- Trigger: {row[0]}")
            found = True
        if not found:
            print("No triggers found.")

if __name__ == "__main__":
    check_triggers()
