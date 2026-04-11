from app.db.session import engine
from sqlalchemy import text

def main():
    with engine.connect() as conn:
        print("--- Last 5 Test Reports ---")
        res = conn.execute(text("SELECT id, module_name, total_tests, passed, failed, created_at FROM test_reports ORDER BY created_at DESC LIMIT 5"))
        for row in res.mappings():
            print(row)

if __name__ == "__main__":
    main()
