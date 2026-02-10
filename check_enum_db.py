import sys
import os
from sqlalchemy import text
from app.core.database import engine

def check_enum():
    with engine.connect() as connection:
        # Query to get enum values in PostgreSQL
        query = text("""
            SELECT enumlabel 
            FROM pg_enum 
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
            WHERE pg_type.typname = 'socialplatform'
            ORDER BY enumsortorder;
        """)
        result = connection.execute(query)
        values = [row[0] for row in result]
        print(f"Enum 'socialplatform' values in DB: {values}")

if __name__ == "__main__":
    # Add backend to path
    sys.path.append(os.path.join(os.path.dirname(__file__)))
    check_enum()
