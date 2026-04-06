import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from sqlalchemy import inspect
from app.db.session import engine
from app.models.user import User

def check_fk():
    inspector = inspect(engine)
    fks = []
    found_schema = None
    for schema in inspector.get_schema_names():
        if inspector.has_table('stations', schema=schema):
            fks = inspector.get_foreign_keys('stations', schema=schema)
            found_schema = schema
            break
            
    if not found_schema:
        print("Table stations not found in any schema.")
        return
        
    print(f"Found stations in schema: {found_schema}")
    
    found = False
    for fk in fks:
        if fk['name'] == 'stations_dealer_id_fkey' or 'dealer_id' in fk['constrained_columns']:
            found = True
            print(f"Foreign Key: {fk['name']}")
            print(f"Constrains column(s): {fk['constrained_columns']} on stations")
            print(f"References table: {fk['referred_table']} (schema: {fk.get('referred_schema')})")
            print(f"References column(s): {fk['referred_columns']}")

    if not found:
        print("FK not found. All FKs on stations:")
        for fk in fks:
            print(fk)

if __name__ == '__main__':
    check_fk()
