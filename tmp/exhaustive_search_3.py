import os
import sys
from sqlalchemy import text

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def search_entire_db_for_len_3():
    print("Exhaustive search for length 3 across ALL tables...")
    query = """
    SELECT table_name, column_name, character_maximum_length
    FROM information_schema.columns
    WHERE character_maximum_length = 3
    AND table_schema = 'public';
    """
    with engine.connect() as conn:
        result = conn.execute(text(query))
        found = False
        for row in result:
            print(f"- Table: {row[0]} | Column: {row[1]} | Max: {row[2]}")
            found = True
        if not found:
            print("Zero columns with length 3 in public schema.")

if __name__ == "__main__":
    search_entire_db_for_len_3()
