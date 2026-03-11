from sqlmodel import Session, create_engine, SQLModel
from app.core.config import settings

# Create database engine with optimized pool settings
engine = create_engine(
    settings.DATABASE_URL, 
    echo=False, # Disable massive logs in dev unless needed
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)

def get_db():
    with Session(engine) as session:
        yield session
