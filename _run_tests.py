"""Debug: print 422 response body from login endpoint"""
import subprocess, sys

code = r'''
import sys, os
os.chdir(r"c:\Users\admin\Desktop\WZ\wezu-backend")
sys.path.insert(0, ".")

# Patch for SQLite JSONB
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
def visit_JSONB(self, type_, **kw):
    return "JSON"
SQLiteTypeCompiler.visit_JSONB = visit_JSONB

# Patch httpx
import httpx
_orig = httpx.Client.__init__
def _patched(self, *a, **kw):
    kw.pop("app", None)
    _orig(self, *a, **kw)
httpx.Client.__init__ = _patched

from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from app.main import app
from app.api import deps
from app.db.session import get_session as db_get_session
from contextlib import asynccontextmanager
from app.core.security import get_password_hash
from app.models.user import User

# Setup In-Memory DB
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SQLModel.metadata.create_all(engine)

# Setup Session & Data
with Session(engine) as session:
    # 1. Create Role
    from app.models.rbac import Role
    role = Role(name="driver", slug="driver", description="Driver", is_system_role=True)
    session.add(role)
    session.commit()
    session.refresh(role)
    
    # 2. Create User manually (to log in with)
    user = User(
        email="login_debug@test.com", 
        phone_number="1234567890",
        full_name="Debug User", 
        hashed_password=get_password_hash("Password123!"),
        is_active=True, 
        is_superuser=False
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Assign role
    user.roles.append(role)
    session.add(user)
    session.commit()

    # Overrides
    def get_session_override():
        return session
    
    app.dependency_overrides[deps.get_db] = get_session_override
    app.dependency_overrides[db_get_session] = get_session_override
    
    @asynccontextmanager
    async def _noop(a):
        yield
    app.router.lifespan_context = _noop
    
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        print("\n--- ATTEMPTING LOGIN ---")
        # Try login
        r = client.post("/api/v1/auth/login", json={
            "username": "login_debug@test.com", 
            "password": "Password123!"
        })
        print(f"LOGIN STATUS: {r.status_code}")
        print(f"LOGIN BODY: {r.text}")
'''

r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
print(r.stdout)
if r.stderr:
    print("STDERR:", r.stderr[-500:])
