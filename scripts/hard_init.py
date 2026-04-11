import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from app.db.session import engine
from sqlmodel import SQLModel, text
from app.models import *

def force_init():
    print("Forcing schema creation...")
    schemas = ["core", "inventory", "rentals", "finance", "logistics", "dealers", "stations"]
    with engine.connect() as conn:
        for s in schemas:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {s};"))
            print(f"Created schema {s}")
        conn.commit()
    
    print("Forcing table creation via SQLModel metadata...")
    # This natively reads all imported models and creates them!
    SQLModel.metadata.create_all(engine)
    print("Tables created successfully!")

if __name__ == "__main__":
    force_init()
