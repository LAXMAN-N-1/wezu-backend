import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.api import deps
from app.core.config import settings

# --- PATCH FOR SQLITE JSONB COMPATIBILITY ---
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

def visit_JSONB(self, type_, **kw):
    return "JSON"

SQLiteTypeCompiler.visit_JSONB = visit_JSONB
# --------------------------------------------

# Use in-memory SQLite for tests
DATABASE_URL = "sqlite://"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@pytest.fixture(name="session")
def session_fixture():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

from app.db.session import get_session as db_get_session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[deps.get_db] = get_session_override
    app.dependency_overrides[db_get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
