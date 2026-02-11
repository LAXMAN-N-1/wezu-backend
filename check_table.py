import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
OUTPUT_FILE = "table_check_result.txt"

try:
    with open(OUTPUT_FILE, "w") as f:
        f.write(f"Checking tables in: {DATABASE_URL}\n")
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        f.write(f"Tables found: {tables}\n")
        if "warehouses" in tables:
            f.write("✅ SUCCESS: 'warehouses' table exists.\n")
        else:
            f.write("❌ FAILURE: 'warehouses' table NOT found.\n")
except Exception as e:
    with open(OUTPUT_FILE, "w") as f:
        f.write(f"Error inspecting database: {e}\n")
