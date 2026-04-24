import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")

engine = create_engine(db_url)
with engine.connect() as conn:
    res = conn.execute(text("SELECT id, run_id, module_name, passed, passed_details FROM test_reports ORDER BY id DESC LIMIT 1"))
    row = res.mappings().first()
    if row:
        print(f"ID: {row['id']}")
        print(f"Run ID: {row['run_id']}")
        print(f"Module: {row['module_name']}")
        print(f"Passed Count: {row['passed']}")
        # Pretty print first 2 passed details
        details = row['passed_details']
        if isinstance(details, str):
             details = json.loads(details)
        print("First 2 Passed Details:")
        print(json.dumps(details[:2], indent=2))
    else:
        print("No reports found.")
