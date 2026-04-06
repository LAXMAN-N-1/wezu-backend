import os
import sys
import sqlalchemy as sa
from sqlalchemy import inspect

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def inspect_table_detailed():
    inspector = inspect(engine)
    columns = inspector.get_columns('audit_logs')
    print("Detailed Columns in 'audit_logs':")
    for col in columns:
        length = col.get('type').length if hasattr(col.get('type'), 'length') else 'None'
        print(f"- {col['name']}: {col['type']} (Length: {length})")

if __name__ == "__main__":
    inspect_table_detailed()
