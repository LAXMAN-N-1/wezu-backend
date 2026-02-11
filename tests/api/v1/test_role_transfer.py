import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, UserRole
from app.models.user import User

def create_superuser_transfer(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@transfer.com")).first()
    if user:
        return user
    user = AdminUser(
        email="admin@transfer.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_transfer_role(client: TestClient, session: Session):
    admin = create_superuser_transfer(session)
    
    # Setup Role
    role = Role(name="Transferable Role", is_active=True)
    session.add(role)
    session.commit()
    
    # Setup Source and Target Users
    u_source = User(email="source@test.com", is_active=True)
    u_target = User(email="target@test.com", is_active=True)
    session.add(u_source)
    session.add(u_target)
    session.commit()
    
    # Assign Role to Source
    ur_source = UserRole(user_id=u_source.id, role_id=role.id, assigned_by=admin.id)
    session.add(ur_source)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Action: Transfer Source -> Target
    payload = {
        "new_user_id": u_target.id,
        "role_id": role.id,
        "reason": "Promotion replacement"
    }
    
    resp = client.post(f"/api/v1/admin/rbac/users/{u_source.id}/roles/transfer", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "transferred" in data["message"].lower()
    
    # Verify DB State
    
    # Source should NOT have role
    source_check = session.exec(
        select(UserRole)
        .where(UserRole.user_id == u_source.id)
        .where(UserRole.role_id == role.id)
    ).first()
    assert source_check is None
    
    # Target SHOULD have role
    target_check = session.exec(
        select(UserRole)
        .where(UserRole.user_id == u_target.id)
        .where(UserRole.role_id == role.id)
    ).first()
    assert target_check is not None
    assert "Promotion replacement" in target_check.notes
    
def test_transfer_fail_no_role(client: TestClient, session: Session):
    admin = create_superuser_transfer(session)
    role = Role(name="Missing Role", is_active=True)
    u1 = User(email="u1_nofail@test.com", is_active=True)
    u2 = User(email="u2_nofail@test.com", is_active=True)
    session.add(role)
    session.add(u1)
    session.add(u2)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    payload = {
        "new_user_id": u2.id,
        "role_id": role.id
    }
    
    # Try to transfer role that u1 doesn't have
    resp = client.post(f"/api/v1/admin/rbac/users/{u1.id}/roles/transfer", json=payload)
    assert resp.status_code == 400
    assert "does not have" in resp.json()["detail"]
