import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, UserRole
from app.models.user import User
from app.models.session import UserSession
from app.models.audit_log import AuditLog

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@remove.com")).first()
    if user:
        return user
    user = AdminUser(
        email="admin@remove.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_remove_role_success(client: TestClient, session: Session):
    admin = create_superuser(session)
    
    # Setup: User with 2 roles
    user = User(email="target_remove@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    r1 = Role(name="Role 1", is_active=True)
    r2 = Role(name="Role 2", is_active=True)
    session.add(r1)
    session.add(r2)
    session.commit()
    
    session.add(UserRole(user_id=user.id, role_id=r1.id))
    session.add(UserRole(user_id=user.id, role_id=r2.id))
    session.commit()
    
    # Setup Session
    sess = UserSession(user_id=user.id, token_id="t_remove", is_active=True)
    session.add(sess)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Action
    resp = client.delete(f"/api/v1/admin/rbac/users/{user.id}/roles/{r1.id}")
    assert resp.status_code == 200
    
    # Verify: UserRole gone
    link = session.exec(select(UserRole).where(UserRole.user_id == user.id).where(UserRole.role_id == r1.id)).first()
    assert link is None
    
    # Verify: One role remains
    count = session.exec(select(func.count()).select_from(UserRole).where(UserRole.user_id == user.id)).one()
    assert count == 1
    
    # Verify: Session invalidated
    session.refresh(sess)
    assert sess.is_active is False
    
    # Verify: Audit Log
    log = session.exec(select(AuditLog).where(AuditLog.action == "remove_role_from_user")).first()
    assert log is not None
    assert log.resource_id == str(user.id)

def test_remove_last_role_failure(client: TestClient, session: Session):
    admin = create_superuser(session)
    user = User(email="last_role@test.com", is_active=True)
    session.add(user)
    
    r1 = Role(name="Role Last", is_active=True)
    session.add(r1)
    session.commit()
    
    session.add(UserRole(user_id=user.id, role_id=r1.id))
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Action: Try to remove only role
    resp = client.delete(f"/api/v1/admin/rbac/users/{user.id}/roles/{r1.id}")
    assert resp.status_code == 400
    assert "last role" in resp.json()["detail"]
    
    # Verify: Still exists
    count = session.exec(select(func.count()).select_from(UserRole).where(UserRole.user_id == user.id)).one()
    assert count == 1
