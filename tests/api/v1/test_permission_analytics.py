import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.rbac import Role, Permission
from app.core.config import settings
from fastapi.testclient import TestClient

def get_auth_headers(client: TestClient, email: str = "perm_analytics_admin@test.com", role: str = "admin"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Perm Analytics Admin",
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

def test_permission_analytics_flow(client, session: Session):
    # 1. Setup Admin
    email = "perm_analytics_admin@test.com"
    headers = get_auth_headers(client, email=email)
    
    # Ensure admin role and superuser
    user = session.exec(select(User).where(User.email == email)).first()
    admin_role = session.exec(select(Role).where(Role.name == "admin")).first()
    if not admin_role:
        admin_role = Role(name="admin", slug="admin", description="Admin")
        session.add(admin_role)
        session.commit()
    
    # Assign role safely
    from app.models.rbac import UserRole
    from sqlalchemy.exc import IntegrityError
    
    link = UserRole(user_id=user.id, role_id=admin_role.id)
    session.add(link)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    
    user.is_superuser = True
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # 2. Create Permissions
    import uuid
    suffix = str(uuid.uuid4())
    used_perm_slug = f"analytics:used:{suffix}"
    unused_perm_slug = f"analytics:unused:{suffix}"
    
    p1 = Permission(slug=used_perm_slug, module="analytics", action="used", description="Used Perm")
    p2 = Permission(slug=unused_perm_slug, module="analytics", action="unused", description="Unused Perm")
    session.add(p1)
    session.add(p2)
    session.commit()
    
    # Assign used_perm to user via admin role (or temp role)
    # Let's add to admin role for simplicity
    admin_role.permissions.append(p1)
    session.add(admin_role)
    session.commit()
    
    # 3. Perform Checks (Generate Log Data)
    # A. Check existing permission (Granted)
    resp = client.get(
        f"{settings.API_V1_STR}/admin/rbac/users/{user.id}/permissions/check?permission={used_perm_slug}",
        headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["has_permission"] == True
    
    # B. Check missing permission (Denied)
    resp = client.get(
        f"{settings.API_V1_STR}/admin/rbac/users/{user.id}/permissions/check?permission={unused_perm_slug}",
        headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["has_permission"] == False
    
    # 4. Fetch Analytics
    resp = client.get(f"{settings.API_V1_STR}/audit/permissions/usage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    # 5. Verify Data
    # Used Permission
    used_entry = next((p for p in data["used_permissions"] if p["slug"] == used_perm_slug), None)
    assert used_entry is not None
    assert used_entry["total_checks"] >= 1
    assert used_entry["granted"] >= 1
    
    # Unused Permission
    # Note: unused_perm_slug WAS checked but denied. So it should appear in used_permissions (as denied)
    # "Unused" in our logic means count=0. 
    # Since we checked unused_perm_slug, it has count >= 1 (denied).
    
    # Let's look for it in used_permissions with denied count
    denied_entry = next((p for p in data["used_permissions"] if p["slug"] == unused_perm_slug), None)
    assert denied_entry is not None
    assert denied_entry["total_checks"] >= 1
    assert denied_entry["denied"] >= 1
    
    # To test strictly "unused", we need a 3rd permission we never check
    strictly_unused_slug = f"analytics:strictly_unused:{suffix}"
    p3 = Permission(slug=strictly_unused_slug, module="analytics", action="unused", description="Strictly Unused")
    session.add(p3)
    session.commit()
    
    # Fetch again
    resp = client.get(f"{settings.API_V1_STR}/audit/permissions/usage", headers=headers)
    data = resp.json()
    
    unused_entry = next((p for p in data["unused_permissions"] if p["slug"] == strictly_unused_slug), None)
    assert unused_entry is not None
