import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def find_all_audit_logs_tables():
    print("Searching for 'audit_logs' in all schemas...")
    query = """
    SELECT table_schema, table_name
    FROM information_schema.tables
    WHERE table_name = 'audit_logs';
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        for row in result:
            print(f"- Schema: {row[0]} | Table: {row[1]}")

if __name__ == "__main__":
    find_all_audit_logs_tables()
