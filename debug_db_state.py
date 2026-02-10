import os
import sys
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

# Force stdout to flush
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
OUTPUT_FILE = "db_diagnostic_result.txt"

def log(msg):
    print(msg)
    with open(OUTPUT_FILE, "a") as f:
        f.write(msg + "\n")

if os.path.exists(OUTPUT_FILE):
    os.remove(OUTPUT_FILE)

log(f"--- Starting Diagnostic ---")
log(f"DATABASE_URL len: {len(DATABASE_URL) if DATABASE_URL else 'None'}")

if not DATABASE_URL:
    log("ERROR: DATABASE_URL not found in environment.")
    sys.exit(1)

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        log("Connection successful.")
        
        # Check alembic version
        try:
            result = connection.execute(text("SELECT * FROM alembic_version"))
            versions = [row[0] for row in result]
            log(f"Alembic Version(s): {versions}")
        except Exception as e:
            log(f"Could not read alembic_version: {e}")

        # Check tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        log(f"Tables found: {tables}")
        
        if "warehouses" in tables:
            log("✅ 'warehouses' table FOUND.")
        else:
            log("❌ 'warehouses' table MISSING.")

except Exception as e:
    log(f"CRITICAL ERROR: {e}")
