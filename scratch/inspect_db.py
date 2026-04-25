
from sqlalchemy import create_engine, select, text
import os
from dotenv import load_dotenv
import sys

# Add the project root to sys.path to import app modules
sys.path.append(os.getcwd())

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def main():
    if not DATABASE_URL:
        print("DATABASE_URL not found in environment")
        return
        
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print(f"Fetching last 10 reports from: {DATABASE_URL}")
        result = conn.execute(text("SELECT id, run_id, module_name, execution_time, created_at FROM test_reports ORDER BY id DESC LIMIT 10"))
        rows = result.fetchall()
        
        if not rows:
            print("No reports found.")
            return

        print(f"{'ID':<5} | {'RunID':<6} | {'Module':<40} | {'Time':<10} | {'Created At'}")
        print("-" * 100)
        for row in rows:
            print(f"{row[0]:<5} | {row[1]:<6} | {row[2]:<40} | {row[3]:<10} | {row[4]}")

if __name__ == "__main__":
    main()
