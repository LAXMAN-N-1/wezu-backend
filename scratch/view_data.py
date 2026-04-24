
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def main():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("--- Last 5 Test Reports ---")
        try:
            res = conn.execute(text("SELECT * FROM test_reports ORDER BY created_at DESC LIMIT 5"))
            for row in res.mappings():
                print(row)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
