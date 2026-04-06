import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def find_len_3_columns():
    print("Finding all columns in DB with Max Length = 3...")
    query = """
    SELECT table_schema, table_name, column_name, data_type
    FROM information_schema.columns
    WHERE character_maximum_length = 3
    AND table_schema NOT IN ('information_schema', 'pg_catalog');
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        found = False
        for row in result:
            print(f"- {row[0]}.{row[1]}.{row[2]} ({row[3]})")
            found = True
        if not found:
            print("No columns with length 3 found.")

if __name__ == "__main__":
    find_len_3_columns()
