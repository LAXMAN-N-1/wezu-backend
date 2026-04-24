import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

engine = create_engine(db_url)
with engine.connect() as conn:
    print("Adding 'passed_details' column to 'test_reports'...")
    try:
        conn.execute(text("ALTER TABLE test_reports ADD COLUMN passed_details JSONB;"))
        conn.commit()
        print("Column added successfully.")
    except Exception as e:
        print(f"Error: {e}")
