import os
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

# Use in-memory SQLite for tests - ensure no database URL is passed
DATABASE_URL = "sqlite://"  # Force in-memory database for tests

# Create engine with proper configuration
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Initialize all tables before any test session
SQLModel.metadata.create_all(engine)

@pytest.fixture(name="session")
def session_fixture():
    with Session(engine) as session:
        yield session

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
