from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel
from app.core.database import engine

def get_session():
    with Session(engine) as session:
        yield session

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

def init_db():
    # Only use for initial bootstrap or small local devs
    # In production, Alembic handles migrations
    SQLModel.metadata.create_all(engine)
