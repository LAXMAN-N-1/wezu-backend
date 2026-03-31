
import os
from sqlalchemy import create_all, create_engine, text
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("DATABASE_URL not found in .env")
    exit(1)

# Fix URL for psycopg2 if needed, or use the one from .env
# The .env has postgresql+psycopg
try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).fetchone()
        print(f"Connection successful: {result}")
except Exception as e:
    print(f"Connection failed: {e}")
