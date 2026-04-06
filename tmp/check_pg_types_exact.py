import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def check_postgres_types_exact():
    print("Checking exact Postgres types for 'audit_logs'...")
    query = """
    SELECT
        attname AS column_name,
        format_type(atttypid, atttypmod) AS data_type
    FROM
        pg_attribute
    WHERE
        attrelid = 'audit_logs'::regclass
        AND attnum > 0
        AND NOT attisdropped;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        for row in result:
            print(f"- {row[0]}: {row[1]}")

if __name__ == "__main__":
    check_postgres_types_exact()
