import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def find_atttypmod_7():
    print("Finding any column with raw atttypmod = 7 (VARCHAR(3))...")
    query = """
    SELECT attname, relname, nspname
    FROM pg_attribute
    JOIN pg_class ON pg_attribute.attrelid = pg_class.oid
    JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid
    WHERE atttypmod = 7
    AND nspname = 'public';
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        found = False
        for row in result:
            print(f"- Schema: {row[2]} | Table: {row[1]} | Column: {row[0]}")
            found = True
        if not found:
            print("No attributes with atttypmod = 7 found.")

if __name__ == "__main__":
    find_atttypmod_7()
