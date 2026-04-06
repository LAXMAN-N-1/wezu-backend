import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def check_postgres_schema():
    print("Checking Postgres information_schema for 'audit_logs'...")
    query = """
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'audit_logs';
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        for row in result:
            print(f"- {row[0]}: {row[1]} (Max Length: {row[2]})")

if __name__ == "__main__":
    check_postgres_schema()
