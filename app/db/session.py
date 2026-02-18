from sqlmodel import create_engine, Session, SQLModel
from app.core.config import settings
from app.models import *

engine = create_engine(
    settings.DATABASE_URL, 
    echo=True,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)

def init_db():
    from sqlmodel import Session, text
    
    # 1. Create Required Schemas
    schemas = ["core", "inventory", "rentals", "finance", "logistics", "dealers", "stations"]
    with engine.connect() as conn:
        for schema in schemas:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema};"))
        conn.commit()
    
    # 2. Create Tables within schemas
    SQLModel.metadata.create_all(engine)
    
    # 3. TimescaleDB initialization
    with Session(engine) as session:
        try:
            # Enable TimescaleDB extension
            session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            
            # Create hypertable for telemetry data if it exists in the metadata
            # This is specifically for the 'telemetry' table in the 'inventory' schema
            session.execute(text(
                "SELECT create_hypertable('inventory.telemetry', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);"
            ))
            session.commit()
            print("TimescaleDB initialized and hypertable 'inventory.telemetry' ensured.")
        except Exception as e:
            print(f"TimescaleDB initialization skipped: {e}")
            session.rollback()
            
        # 4. Seed Initial Data (Roles)
        from app.db.initial_data import seed_roles
        seed_roles(session)

def get_session():
    with Session(engine) as session:
        yield session
