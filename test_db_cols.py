from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("DATABASE_URL")
engine = create_engine(url)
inspector = inspect(engine)
cols = [c["name"] for c in inspector.get_columns("users")]
print("User Columns:", cols)
