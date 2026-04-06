import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def check_postgres_schema_to_file():
    print("Checking Postgres information_schema for 'audit_logs' (length checking)...")
    query = """
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'audit_logs';
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        with open('tmp/pg_schema_full.txt', 'w') as f:
            for row in result:
                f.write(f"- {row[0]}: {row[1]} (Max Length: {row[2]})\n")
    print("Full Postgres schema written to tmp/pg_schema_full.txt")

if __name__ == "__main__":
    check_postgres_schema_to_file()
