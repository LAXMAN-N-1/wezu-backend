import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def found_exact_length_3():
    print("Searching for EXACT length 3 constraint in 'audit_logs'...")
    query = """
    SELECT
        f.attname AS column_name,
        v.atttypmod - 4 AS max_length
    FROM
        pg_attribute AS f
    JOIN
        pg_type AS t ON f.atttypid = t.oid
    JOIN
        pg_attribute AS v ON v.attrelid = f.attrelid AND v.attname = f.attname
    WHERE
        f.attrelid = 'audit_logs'::regclass
        AND f.attnum > 0
        AND NOT f.attisdropped
        AND v.atttypmod > 0;
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        found = False
        for row in result:
            print(f"- Column: {row[0]} | Max Length: {row[1]}")
            found = True
        if not found:
            print("No columns with specific length found.")

if __name__ == "__main__":
    found_exact_length_3()
