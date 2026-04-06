import os
import sys
import sqlalchemy as sa
from sqlalchemy import inspect

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import engine

def inspect_table_to_file():
    inspector = inspect(engine)
    columns = inspector.get_columns('audit_logs')
    with open('tmp/db_inspect_full.txt', 'w') as f:
        f.write("Detailed Columns in 'audit_logs':\n")
        for col in columns:
            length = col.get('type').length if hasattr(col.get('type'), 'length') else 'None'
            f.write(f"- {col['name']}: {col['type']} (Length: {length})\n")
    print("Full inspection written to tmp/db_inspect_full.txt")

if __name__ == "__main__":
    inspect_table_to_file()
