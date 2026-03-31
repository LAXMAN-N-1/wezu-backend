import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, UTC, timedelta
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, UserRole
from app.models.user import User
from app.models.session import UserSession

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@assign.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='1758566462', 
        email="admin@assign.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_assign_role_to_user(client: TestClient, session: Session):
    admin = create_superuser(session)
    
    # Setup
    role = Role(name="Assigned Role", is_active=True)
    session.add(role)
    perm = Permission(slug="assigned:perm", module="mod", action="act")
    session.add(perm)
    session.commit()
    role.permissions.append(perm)
    session.commit()
    
    target_user = User(phone_number='3023562286', email="target@assign.com", is_active=True)
    session.add(target_user)
    session.commit()
    
    # Active Session
    sess = UserSession(user_id=target_user.id, token_id="t1", is_active=True)
    session.add(sess)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    # Action
    payload = {
        "role_id": role.id,
        "notes": "Testing assignment",
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat()
    }
    
    resp = client.post(f"/api/v1/admin/rbac/users/{target_user.id}/roles", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["success"] is True
    assert "assigned:perm" in data["active_permissions"]
    
    # Verify DB Link
    link = session.exec(select(UserRole).where(UserRole.user_id == target_user.id)).first()
    assert link is not None
    assert link.role_id == role.id
    assert link.notes == "Testing assignment"
    assert link.expires_at is not None
    assert link.assigned_by == admin.id
    
    # Verify Session Invalidation
    session.refresh(sess)
    assert sess.is_active is False

def test_assign_role_update_existing(client: TestClient, session: Session):
    admin = create_superuser(session)
    role = Role(name="Existing Role", is_active=True)
    session.add(role)
    session.commit()
    
    target_user = User(phone_number='7462806662', email="update@assign.com", is_active=True)
    session.add(target_user)
    session.commit()
    
    # Pre-exist
    session.add(UserRole(user_id=target_user.id, role_id=role.id, notes="Old"))
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    
    payload = {
        "role_id": role.id,
        "notes": "Updated Note"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/users/{target_user.id}/roles", json=payload)
    assert resp.status_code == 200
    
    # Verify Update
    link = session.exec(select(UserRole).where(UserRole.user_id == target_user.id)).first()
    assert link.notes == "Updated Note"
