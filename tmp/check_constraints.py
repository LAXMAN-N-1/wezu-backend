import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def check_sql_constraints():
    print("Checking SQL constraints on 'audit_logs'...")
    query = """
    SELECT conname, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'audit_logs'::regclass;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        found = False
        for row in result:
            print(f"- Constraint: {row[0]} | Def: {row[1]}")
            found = True
        if not found:
            print("No constraints found.")

if __name__ == "__main__":
    check_sql_constraints()
