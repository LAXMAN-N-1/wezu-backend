import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

try:
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    columns = inspector.get_columns("dealer_profiles")
    print(f"Columns in 'dealer_profiles':")
    for column in columns:
        print(f"- {column['name']} ({column['type']})")
except Exception as e:
    print(f"Error inspecting table: {e}")
