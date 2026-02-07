import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, timedelta
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, UserRole
from app.models.user import User

def create_superuser_list(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@list.com")).first()
    if user:
        return user
    user = AdminUser(
        email="admin@list.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        full_name="Admin Lister"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_get_user_roles(client: TestClient, session: Session):
    admin = create_superuser_list(session)
    
    # Setup User
    user = User(email="target_list@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    # Setup Roles
    r1 = Role(name="Active Role", is_active=True)
    r2 = Role(name="Expired Role", is_active=True)
    r3 = Role(name="Future Role", is_active=True)
    session.add(r1)
    session.add(r2)
    session.add(r3)
    session.commit()
    
    # Assign Roles
    # 1. Active
    ur1 = UserRole(
        user_id=user.id, 
        role_id=r1.id, 
        assigned_by=admin.id,
        notes="Active Note"
    )
    # 2. Expired
    ur2 = UserRole(
        user_id=user.id, 
        role_id=r2.id, 
        assigned_by=admin.id,
        expires_at=datetime.utcnow() - timedelta(days=1)
    )
    # 3. Future
    ur3 = UserRole(
        user_id=user.id, 
        role_id=r3.id, 
        assigned_by=admin.id,
        effective_from=datetime.utcnow() + timedelta(days=1)
    )
    
    session.add(ur1)
    session.add(ur2)
    session.add(ur3)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Action
    resp = client.get(f"/api/v1/admin/rbac/users/{user.id}/roles")
    assert resp.status_code == 200
    data = resp.json()
    
    assert len(data) == 3
    
    # Check Active
    active = next(r for r in data if r["role_id"] == r1.id)
    assert active["is_active"] is True
    assert active["role_name"] == "Active Role"
    assert active["assigned_by_name"] == "Admin Lister" or active["assigned_by_name"] == "admin@list.com"
    assert active["notes"] == "Active Note"
    
    # Check Expired
    expired = next(r for r in data if r["role_id"] == r2.id)
    assert expired["is_active"] is False
    assert expired["role_name"] == "Expired Role"
    
    # Check Future
    future = next(r for r in data if r["role_id"] == r3.id)
    assert future["is_active"] is False
    assert future["role_name"] == "Future Role"
