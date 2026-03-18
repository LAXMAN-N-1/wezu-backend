import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Permission

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@roles.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='1862748912', 
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def setup_permissions(session):
    # Module A
    p1 = Permission(slug="mod_a:read", module="mod_a", action="read", description="Read A")
    p2 = Permission(slug="mod_a:write", module="mod_a", action="write")
    
    # Module B
    p3 = Permission(slug="mod_b:view", module="mod_b", action="view")
    
    session.add(p1)
    session.add(p2)
    session.add(p3)
    session.commit()

def test_list_permissions_grouped(client: TestClient, session: Session):
    admin = create_superuser(session)
    setup_permissions(session)
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    resp = client.get("/api/v1/admin/rbac/permissions")
    assert resp.status_code == 200
    data = resp.json()
    
    assert "modules" in data
    modules = data["modules"]
    
    # Check Mod A
    mod_a = next((m for m in modules if m["module"] == "mod_a"), None)
    assert mod_a is not None
    assert mod_a["label"] == "Mod A"
    assert len(mod_a["permissions"]) >= 2
    
    p1 = next((p for p in mod_a["permissions"] if p["id"] == "mod_a:read"), None)
    assert p1 is not None
    assert p1["action"] == "read"
    assert p1["description"] == "Read A"
    assert p1["resource"] == "mod_a"
    
    # Check Mod B
    mod_b = next((m for m in modules if m["module"] == "mod_b"), None)
    assert mod_b is not None
    assert len(mod_b["permissions"]) >= 1
