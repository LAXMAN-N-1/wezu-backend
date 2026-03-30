import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select, and_
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

# Use PostgreSQL for tests (dedicated test database is required)
# Read from environment variable if available, otherwise fallback to a default
DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wezu_test")

# Create engine with proper configuration
# Removed StaticPool as it is primarily for SQLite in-memory and causes TypeErrors with PostgreSQL
engine = create_engine(DATABASE_URL)

# Initialize all tables before any test session
SQLModel.metadata.create_all(engine)

@pytest.fixture(name="session")
def session_fixture():
    from sqlmodel import Session
    from sqlalchemy import text
    
    with Session(engine) as session:
        # Seed basic driver role if missing
        from app.models.rbac import Role
        driver_role = session.exec(select(Role).where(Role.name == "driver")).first()
        if not driver_role:
            driver_role = Role(
                name="driver", 
                slug="driver",
                description="Driver role",
                is_system_role=True
            )
            session.add(driver_role)
            session.commit()
            
        yield session
        
        # Teardown logic: Use TRUNCATE CASCADE to handle circular foreign keys
        # We need a list of all tables in the correct order or just truncate all
        tables = SQLModel.metadata.tables.keys()
        if tables:
            truncate_stmt = f"TRUNCATE TABLE {', '.join(tables)} CASCADE;"
            session.execute(text(truncate_stmt))
            session.commit()

@pytest.fixture(autouse=True)
def seed_basics(session: Session):
    """
    Seed minimal roles, menus, permissions and a superuser so RBAC/user tests have baseline data.
    Data is cleared after each test by session_fixture teardown.
    """
    from app.models.rbac import Role, Permission
    from app.models.menu import Menu
    from app.models.role_right import RoleRight
    from app.models.user import User, UserStatus, UserType
    from app.core.security import get_password_hash

    # Check if admin role already exists (to avoid duplicate seed errors in same session)
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if not admin_role:
        admin_role = Role(name="admin", description="Super Admin", category="system", level=100)
        session.add(admin_role)
        session.commit()
        session.refresh(admin_role)

    # Menu
    menu = session.exec(select(Menu).where(Menu.name == "dashboard")).first()
    if not menu:
        menu = Menu(name="dashboard", display_name="Dashboard", route="/dashboard", icon="home")
        session.add(menu)
        session.commit()
        session.refresh(menu)

    # Permission
    perm = session.exec(select(Permission).where(Permission.slug == "dashboard:view")).first()
    if not perm:
        perm = Permission(slug="dashboard:view", module="dashboard", action="view", scope="all")
        session.add(perm)
        session.commit()
        session.refresh(perm)

    # RoleRight and RolePermission association
    rr = session.exec(select(RoleRight).where(and_(RoleRight.role_id == admin_role.id, RoleRight.menu_id == menu.id))).first()
    if not rr:
        rr = RoleRight(role_id=admin_role.id, menu_id=menu.id, can_view=True, can_create=True, can_edit=True, can_delete=True)
        session.add(rr)
        session.commit()

    # Superuser
    admin_user = session.exec(select(User).where(User.email == "admin@test.com")).first()
    if not admin_user:
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

