from sqlmodel import Session, SQLModel, create_engine
from app.core.config import settings
from app.core.database import engine
# Removed bulk import to prevent circularities

print(f"DEBUG: app/db/session.py - DATABASE_URL: {settings.DATABASE_URL}")
try:
    engine = create_engine(
        settings.DATABASE_URL, 
        echo=settings.SQLALCHEMY_ECHO,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True
    )
    print("DEBUG: app/db/session.py - Engine created")
except Exception as e:
    print(f"DEBUG: app/db/session.py - Engine creation FAILED: {e}")
    import traceback
    traceback.print_exc()
    raise

def init_db():
    from sqlmodel import Session, text
    
    # 1. Create Required Schemas
    schemas = ["core", "inventory", "rentals", "finance", "logistics", "dealers", "stations"]
    with engine.connect() as conn:
        for schema in schemas:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema};"))
        conn.commit()
    
    # 2. Create Tables within schemas - Disabling temporarily to prevent hangs in dev
    # SQLModel.metadata.create_all(engine)
    
    # 3. TimescaleDB initialization
    with Session(engine) as session:
        try:
            # Enable TimescaleDB extension - silence noise
            session.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            session.commit()
        except Exception as e:
            import logging
            logging.warning(f"TimescaleDB extension check failed: {e}")
            session.rollback()

        # 4. Seed Initial Data (Roles)
        from app.db.initial_data import seed_roles
        seed_roles(session)
        session.commit()

def get_session():
    with Session(engine) as session:
        yield session
