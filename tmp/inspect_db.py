import os
import sys
import sqlalchemy as sa
from sqlalchemy import inspect

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def inspect_table():
    inspector = inspect(engine)
    columns = inspector.get_columns('audit_logs')
    print("Columns in 'audit_logs':")
    for col in columns:
        print(f"- {col['name']} ({col['type']})")

if __name__ == "__main__":
    inspect_table()
