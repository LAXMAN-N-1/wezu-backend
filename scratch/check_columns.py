import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
print(f"DATABASE_URL: {db_url}")

engine = create_engine(db_url)
columns = [c['name'] for c in inspect(engine).get_columns('test_reports')]
print(f"Columns: {columns}")
