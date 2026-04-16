import os
import pytest
import sys
import time
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from unittest.mock import MagicMock

# --- MOCK FIREBASE BEFORE APP IMPORTS ---
mock_firebase = MagicMock()
sys.modules["firebase_admin"] = mock_firebase
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.messaging"] = MagicMock()

# --- CONFIG OVERRIDE BEFORE APP IMPORTS ---
from app.core.config import settings
_PROD_DATABASE_URL: str = settings.DATABASE_URL
settings.ENVIRONMENT = "test"
settings.DATABASE_URL = "sqlite://"

# --- NOW IMPORT APP MODULES ---
from app.main import app
from app.api import deps
from app.core import database
from app.db import session as db_session
from app.middleware.rate_limit import limiter
from app.services.test_report_service import test_report_service
limiter.enabled = False

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

# Patch global engines
database.engine = engine
db_session.engine = engine

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
        session.rollback()
        for table in reversed(SQLModel.metadata.sorted_tables):
            try:
                session.execute(table.delete())
            except Exception:
                session.rollback()
        session.commit()


@pytest.fixture(autouse=True)
def seed_basics(session: Session):
    """
    Seed minimal roles, menus, permissions and a superuser so RBAC/user tests have baseline data.
    Data is cleared after each test by session_fixture teardown.
    """
    # Role
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
    rr = session.exec(select(RoleRight).where(RoleRight.role_id == admin_role.id, RoleRight.menu_id == menu.id)).first()
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


@pytest.fixture(name="admin_token_headers")
def admin_token_headers_fixture(client: TestClient):
    login_data = {
        "username": "admin@test.com",
        "password": "password",
    }
    r = client.post("/api/v1/auth/token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


@pytest.fixture(name="normal_user_token_headers")
def normal_user_token_headers_fixture(client: TestClient, normal_user: User):
    login_data = {
        "username": "normal_user@example.com",
        "password": "password",
    }
    r = client.post("/api/v1/auth/token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Hook to capture test results and save them to the production database,
    grouping by the actual test file/module name.
    """
    stats = terminalreporter.stats
    
    # We will accumulate results grouped by file path (e.g., tests/test_login.py)
    modules = {}

    def get_module(nodeid):
        return nodeid.split("::")[0] if "::" in nodeid else "unknown_module"

    # Process all reports
    for outcome in ["passed", "failed", "skipped", "error"]:
        for report in stats.get(outcome, []):
            if hasattr(report, "when") and report.when != "call" and outcome == "passed":
                continue # Skip setup/teardown passes
            mod = get_module(report.nodeid)
            if mod not in modules:
                modules[mod] = {"passed": 0, "failed": 0, "skipped": 0, "error": 0, "failures": [], "errors": []}
            
            modules[mod][outcome] += 1
            
            if outcome == "failed":
                modules[mod]["failures"].append({
                    "nodeid": report.nodeid,
                    "message": str(report.longreprtext) if hasattr(report, 'longreprtext') else "No traceback"
                })
            elif outcome == "error":
                modules[mod]["errors"].append({
                    "nodeid": report.nodeid,
                    "message": str(report.longreprtext) if hasattr(report, 'longreprtext') else "Error during setup/teardown"
                })

    duration = time.time() - getattr(terminalreporter, '_sessionstarttime', time.time())
    
    # If no modules found but total tests ran (maybe just nothing failed/passed?), fallback:
    if not modules:
        passed = len(stats.get('passed', []))
        failed = len(stats.get('failed', []))
        skipped = len(stats.get('skipped', []))
        error = len(stats.get('error', []))
        total = passed + failed + skipped + error
        if total > 0:
            modules["pytest_run"] = {"passed": passed, "failed": failed, "skipped": skipped, "error": error, "failures": [], "errors": []}

    report_data = {}
    for mod, data in modules.items():
        total_mod = data["passed"] + data["failed"] + data["skipped"] + data["error"]
        report_data[mod] = {
            "total_tests": total_mod,
            "passed": data["passed"],
            "failed": data["failed"] + data["error"],
            "skipped": data["skipped"],
            "failures": data["failures"],
            "errors": data["errors"],
            "execution_time": f"{round(duration, 2)}s",
            "environment": os.getenv("ENVIRONMENT", "local_test"),
            "created_by": os.getenv("USER", os.getenv("USERNAME", "dev"))
        }

    print(f"\n[REPORT] Saving results for {len(report_data)} module(s) to production database...")

    try:
        from sqlmodel import Session
        from sqlalchemy import create_engine as _create_engine
        # Use the original prod URL (captured before settings override to sqlite://)
        _prod_engine = _create_engine(_PROD_DATABASE_URL)
        with Session(_prod_engine) as db:
            test_report_service.save_from_dict(db, report_data)
            print("[REPORT] Success: Test results stored in 'test_reports' table.")
    except Exception as e:
        print(f"[REPORT] Error saving results to DB: {e}")

