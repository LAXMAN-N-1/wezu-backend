from sqlmodel import Session, create_engine
from app.core.config import settings

# Create database engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=False)

def get_db():
    with Session(engine) as session:
        yield session
