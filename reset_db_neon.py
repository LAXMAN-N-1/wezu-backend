import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def reset_database():
    print("--- Robust Database Reset v2 ---")
    schemas = ["core", "inventory", "stations", "rentals", "finance", "dealers", "logistics", "public"]
    
    with engine.connect() as conn:
        for schema in schemas:
            print(f"Dropping and recreating schema: {schema}")
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE;"))
            conn.execute(text(f"CREATE SCHEMA {schema} AUTHORIZATION neondb_owner;"))
            conn.execute(text(f"GRANT ALL ON SCHEMA {schema} TO neondb_owner;"))
            conn.execute(text(f"GRANT ALL ON SCHEMA {schema} TO public;"))
        
        conn.execute(text("ALTER USER neondb_owner SET search_path TO public,core,dealers,finance,rentals,inventory,stations,logistics;"))
        conn.commit()
    print("Database reset and permissions granted.")

if __name__ == "__main__":
    reset_database()
