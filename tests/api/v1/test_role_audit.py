import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.rbac import Role
from app.models.audit_log import AuditLog
from app.core.config import settings
from fastapi.testclient import TestClient

def get_auth_headers(client: TestClient, email: str = "role_audit_admin@test.com", role: str = "admin"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Role Audit Admin",
            "phone_number": str(abs(hash(email)))[:10].ljust(10, '0')
        },
    )
    
    # 2. Login
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": email,
            "password": "Password123!"
        },
    )
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}

def test_role_audit_flow(client, session: Session):
    # 1. Setup Admin
    admin_email = "role_audit_admin@test.com"
    headers = get_auth_headers(client, email=admin_email)
    
    # Make sure user is admin in DB
    user = session.exec(select(User).where(User.email == admin_email)).first()
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if not admin_role:
        admin_role = Role(name="admin", slug="admin", description="Admin")
        session.add(admin_role)
        session.commit()
    
    if admin_role not in user.roles:
        user.roles.append(admin_role)
        session.add(user)
    
    # Ensure superuser for admin_rbac endpoints
    user.is_superuser = True
    session.add(user)
    session.commit()
    session.refresh(user)
        
    # 2. Create Role
    import uuid
    unique_suffix = str(uuid.uuid4())
    role_name = f"Audit Test Role {unique_suffix}"
    
    role_data = {
        "name": role_name,
        "description": "Role for auditing",
        "permissions": []
    }
    resp = client.post(f"{settings.API_V1_STR}/admin/rbac/roles", headers=headers, json=role_data)
    # If 403, might need superuser. admin_rbac uses get_current_active_superuser often.
    # Let's check admin_rbac.py dependencies.
    # It uses deps.get_current_active_superuser.
    # user.is_superuser needs to be True.
    if resp.status_code == 403:
        user.is_superuser = True
        session.add(user)
        session.commit()
        resp = client.post(f"{settings.API_V1_STR}/admin/rbac/roles", headers=headers, json=role_data)
        
    assert resp.status_code == 200, f"Role creation failed: {resp.text}"
    role_id = resp.json()["id"]
    
    # 3. Update Role
    update_data = {"description": "Updated Description"}
    client.put(f"{settings.API_V1_STR}/admin/rbac/roles/{role_id}", headers=headers, json=update_data)
    
    # 3b. Assign Permissions
    # Create a permission first
    from app.models.rbac import Permission
    perm_slug = f"audit:test:{unique_suffix}"
    perm = Permission(slug=perm_slug, module="audit", action="test", description="Audit Test Perm")
    session.add(perm)
    session.commit()
    
    assign_data = {
        "permissions": [perm_slug],
        "mode": "append"
    }
    client.post(f"{settings.API_V1_STR}/admin/rbac/roles/{role_id}/permissions", headers=headers, json=assign_data)
    
    # 4. Check Audit Log
    resp = client.get(f"{settings.API_V1_STR}/audit/roles/{role_id}/changes", headers=headers)
    assert resp.status_code == 200
    logs = resp.json()["logs"]
    
    # Expect creation, update, and permission update logs
    actions = [l["action"] for l in logs]
    details = [l["details"] for l in logs]
    
    assert "create_role" in actions
    assert "update_role" in actions
    assert "update_role_permissions" in actions
    
    # Verify details contain expected changes
    update_log = next(l for l in logs if l["action"] == "update_role")
    assert "Description changed" in update_log["details"] or "Description" in update_log["details"]
    
    perm_log = next(l for l in logs if l["action"] == "update_role_permissions")
    assert "Added" in perm_log["details"]
    assert perm_slug in perm_log["details"]
    
    # 5. Delete Role
    client.delete(f"{settings.API_V1_STR}/admin/rbac/roles/{role_id}", headers=headers)
    
    # 6. Check Audit Log again
    resp = client.get(f"{settings.API_V1_STR}/audit/roles/{role_id}/changes", headers=headers)
    logs = resp.json()["logs"]
    actions = [l["action"] for l in logs]
    assert "delete_role" in actions
