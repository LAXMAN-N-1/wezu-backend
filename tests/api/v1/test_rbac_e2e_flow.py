import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, timedelta
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, Permission, UserRole
from app.models.user import User
from app.models.session import UserSession

def create_superuser(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@e2e.com")).first()
    if user:
        return user
    user = AdminUser(
        email="admin@e2e.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_rbac_full_lifecycle(client: TestClient, session: Session):
    admin = create_superuser(session)
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # 1. Setup Data: Create Permissions
    p1 = Permission(slug="e2e:create", module="e2e", action="create")
    p2 = Permission(slug="e2e:read", module="e2e", action="read")
    session.add(p1)
    session.add(p2)
    session.commit()
    
    # 2. Setup Data: Create Users
    user = User(email="e2e_user@test.com", is_active=True)
    session.add(user)
    session.commit()
    
    # login session
    user_session = UserSession(user_id=user.id, token_id="e2e_token", is_active=True)
    session.add(user_session)
    session.commit()

    # 3. Create Role (POST /roles) - Assumed endpoint exists or using DB directly if not focus
    # Let's assume /roles endpoint exists based on code context, if not I'll use DB
    # Using DB for reliability of this specific test scope unless requested to test that too
    role = Role(name="E2E Manager", is_active=True)
    session.add(role)
    session.commit()
    
    # 4. Assign Permissions to Role (POST /roles/{id}/permissions)
    payload_perm = {
        "permissions": ["e2e:create", "e2e:read"],
        "mode": "overwrite"
    }
    resp = client.post(f"/api/v1/admin/rbac/roles/{role.id}/permissions", json=payload_perm)
    assert resp.status_code == 200
    assert len(resp.json()["active_permissions"]) == 2
    
    # 5. Assign Role to User (POST /users/{id}/roles)
    payload_role = {
        "role_id": role.id,
        "notes": "E2E Assignment",
        "effective_from": datetime.utcnow().isoformat()
    }
    resp = client.post(f"/api/v1/admin/rbac/users/{user.id}/roles", json=payload_role)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    
    # Verify Side Effect: Session Invalidation
    session.refresh(user_session)
    assert user_session.is_active is False
    
    # 6. Check Specific Permission (GET /users/{id}/permissions/check)
    resp = client.get(
        f"/api/v1/admin/rbac/users/{user.id}/permissions/check",
        params={"permission": "e2e:create"}
    )
    assert resp.status_code == 200
    assert resp.json()["has_permission"] is True
    assert resp.json()["granted_by_role"] == "E2E Manager"
    
    # 7. Get All Permissions (GET /users/{id}/permissions)
    resp = client.get(f"/api/v1/admin/rbac/users/{user.id}/permissions")
    assert resp.status_code == 200
    data = resp.json()
    modules = {m["module"]: m for m in data["modules"]}
    assert "e2e" in modules
    assert len(modules["e2e"]["permissions"]) == 2

    # 8. Duplicate Role (POST /roles/{id}/duplicate)
    payload_dup = {"new_name": "E2E Manager Copy"}
    resp = client.post(f"/api/v1/admin/rbac/roles/{role.id}/duplicate", json=payload_dup)
    assert resp.status_code == 200
    dup_role_id = resp.json()["id"]
    
    # Verify duplicate has permissions
    dup_role = session.get(Role, dup_role_id)
    assert len(dup_role.permissions) == 2
    
    # 9. Delete Role (DELETE /roles/{id})
    # First, need to remove users or ensure delete handles it (Soft delete usually ok)
    resp = client.delete(f"/api/v1/admin/rbac/roles/{dup_role_id}")
    # Note: Soft delete might return success
    assert resp.status_code == 200 
    
    session.refresh(dup_role)
    assert dup_role.is_active is False
