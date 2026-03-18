import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
import sys
from unittest.mock import MagicMock

# --- MOCK FIREBASE BEFORE APP IMPORTS ---
# Prevents "Firebase Init Error" from top-level module code
mock_firebase = MagicMock()
sys.modules["firebase_admin"] = mock_firebase
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.messaging"] = MagicMock()

from app.main import app
from app.api import deps
from app.core.config import settings
from app.core import database
from app.core.security import get_password_hash
from app.models.rbac import Role, Permission
from app.models.role_right import RoleRight
from app.models.menu import Menu
from app.models.user import User, UserStatus, UserType

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

from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if type(dbapi_connection) is sqlite3.Connection:
        cursor = dbapi_connection.cursor()
        cursor.execute("ATTACH DATABASE ':memory:' AS core")
        cursor.execute("ATTACH DATABASE ':memory:' AS dealers")
        cursor.execute("ATTACH DATABASE ':memory:' AS finance")
        cursor.execute("ATTACH DATABASE ':memory:' AS rentals")
        cursor.execute("ATTACH DATABASE ':memory:' AS inventory")
        cursor.execute("ATTACH DATABASE ':memory:' AS stations")
        cursor.execute("ATTACH DATABASE ':memory:' AS logistics")
        cursor.execute("ATTACH DATABASE ':memory:' AS public")
        cursor.close()

# Initialize all tables before any test session
SQLModel.metadata.create_all(engine)

@pytest.fixture(name="session")
def session_fixture():
    with Session(engine) as session:
        # Seed basic roles for tests
        from app.models.rbac import Role
        if not session.exec(select(Role).where(Role.name == "driver")).first():
            driver_role = Role(
                name="driver", 
                slug="driver",
                description="Driver role",
                is_system_role=True
            )
            session.add(driver_role)
            try:
                session.commit()
            except Exception:
                session.rollback()
            
        yield session
        # Teardown: delete all data
        for table in reversed(SQLModel.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture(autouse=True)
def seed_basics(session: Session):
    """
    Seed minimal roles, menus, permissions and a superuser so RBAC/user tests have baseline data.
    Data is cleared after each test by session_fixture teardown.
    """
    # Role
    admin_role = Role(name="admin", description="Super Admin", category="system", level=100)
    session.add(admin_role)
    session.commit()
    session.refresh(admin_role)

    # Menu
    menu = Menu(name="dashboard", display_name="Dashboard", route="/dashboard", icon="home")
    session.add(menu)
    session.commit()
    session.refresh(menu)

    # Permission
    perm = Permission(slug="dashboard:view", module="dashboard", action="view", scope="all")
    session.add(perm)
    session.commit()
    session.refresh(perm)

    # RoleRight and RolePermission association
    rr = RoleRight(role_id=admin_role.id, menu_id=menu.id, can_view=True, can_create=True, can_edit=True, can_delete=True)
    session.add(rr)
    session.commit()

    # Superuser
    admin_user = User(
        phone_number="9999999999",
        email="admin@test.com",
        full_name="Admin",
        hashed_password=get_password_hash("password"),
        is_superuser=True,
        status=UserStatus.ACTIVE,
        user_type=UserType.ADMIN,
        role_id=admin_role.id,
    )
    session.add(admin_user)
    session.commit()

from app.db.session import get_session as db_get_session

# --- PATCH FOR HTTPX 0.28+ / STARLETTE COMPATIBILITY ---
import httpx
_original_httpx_init = httpx.Client.__init__

def _patched_httpx_init(self, *args, **kwargs):
    kwargs.pop("app", None)
    _original_httpx_init(self, *args, **kwargs)

httpx.Client.__init__ = _patched_httpx_init
# --------------------------------------------------------

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[deps.get_db] = get_session_override
    app.dependency_overrides[database.get_db] = get_session_override
    app.dependency_overrides[db_get_session] = get_session_override
    
    # Replace lifespan with a no-op to prevent init_db/start_scheduler
    # from connecting to the real database or starting background jobs
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.router.lifespan_context = original_lifespan
    
    app.dependency_overrides.clear()

@pytest.fixture(name="normal_user")
def normal_user_fixture(session: Session):
    from app.models.user import User
    from app.core.security import get_password_hash
    user = User(
        email="normal_user@example.com",
        hashed_password=get_password_hash("password"),
        full_name="Normal User",
        phone_number="5555555555",
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

