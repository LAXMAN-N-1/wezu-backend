import time
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.database import engine
from sqlmodel import SQLModel
# Import models to build metadata
from app.models import *

print("Starting safe DB reset...")

# Get all tables
with engine.connect() as conn:
    print("Finding tables...")
    result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"))
    tables = [r[0] for r in result]
    print(f"Found {len(tables)} tables to drop.")
    
    conn.execute(text("SET statement_timeout = 5000;")) # Don't hang forever
    
    print("Dropping tables...")
    try:
        if tables:
            drop_stmt = "DROP TABLE IF EXISTS " + ", ".join([f'"{t}"' for t in tables]) + " CASCADE"
            conn.execute(text(drop_stmt))
            conn.commit()
    except Exception as e:
        print(f"Error dropping tables: {e}")
        conn.rollback()
        
    print("Checking alembic versions...")
    conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    conn.commit()

print("Rebuilding tables from metadata...")
try:
    SQLModel.metadata.create_all(engine)
    print("✅ Tables rebuilt successfully!")
except Exception as e:
    print(f"❌ Failed to create tables: {e}")
