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
    user = AdminUser(
        email="admin@roles.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_create_permission_success(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    payload = {
        "slug": "custom:feature:access",
        "module": "custom",
        "action": "access",
        "description": "Custom Feature",
        "scope": "region"
    }
    
    resp = client.post("/api/v1/admin/rbac/permissions", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["slug"] == "custom:feature:access"
    assert data["scope"] == "region"
    assert data["id"] is not None
    
    # Verify DB
    perm = session.exec(select(Permission).where(Permission.slug == "custom:feature:access")).first()
    assert perm is not None
    assert perm.scope == "region"

def test_create_permission_duplicate_slug(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Existing perm
    p1 = Permission(slug="exist:p1", module="exist", action="read")
    session.add(p1)
    session.commit()
    
    payload = {
        "slug": "exist:p1",
        "module": "exist",
        "action": "write"
    }
    
    resp = client.post("/api/v1/admin/rbac/permissions", json=payload)
    assert resp.status_code == 400
    assert "slug already exists" in resp.json()["detail"]
