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
    SQLModel.metadata.create_all(engine)
    
    # TimescaleDB initialization
    with Session(engine) as session:
        # TimescaleDB initialization (Creating extension requires system install)
        # try:
        #     session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
        #     
        #     # Create hypertable for telematics if it doesn't exist
        #     session.execute(text(
        #         "SELECT create_hypertable('telemetics_data', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);"
        #     ))
        #     session.commit()
        #     print("TimescaleDB hypertable 'telemetics_data' ensured.")
        # except Exception as e:
        #     print(f"Hypertable creation info/error: {e} (TimescaleDB might not be installed, skipping)")
        #     session.rollback()
            
        # 3. Seed Initial Data (Roles)
        from app.db.initial_data import seed_roles
        seed_roles(session)

def get_session():
    with Session(engine) as session:
        yield session
