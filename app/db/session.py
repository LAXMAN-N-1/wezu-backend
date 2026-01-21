from sqlmodel import create_engine, Session, SQLModel
from app.core.config import settings
from app.models import *

engine = create_engine(settings.DATABASE_URL, echo=True)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
