import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.rbac import Role
from app.core.config import settings
from fastapi.testclient import TestClient
from datetime import datetime, UTC, timedelta

def get_auth_headers(client: TestClient, email: str = "data_audit_admin@test.com", role: str = "admin"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Data Audit Admin",
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

def test_data_access_audit_filters(client, session: Session):
    # 1. Setup Admin
    email = "data_audit_admin@test.com"
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
    
    # 2. Generate Audit Data (Manually injection for test speed)
    from app.services.audit_service import AuditService
    import uuid
    
    # Log 1: User Resource
    res_id_1 = str(uuid.uuid4())
    AuditService.log_action(
        db=session,
        user_id=user.id,
        action="update_user",
        resource_type="user",
        resource_id=res_id_1,
        details="Updated user profile"
    )
    
    # Log 2: Battery Resource
    res_id_2 = str(uuid.uuid4())
    AuditService.log_action(
        db=session,
        user_id=user.id,
        action="swap_battery",
        resource_type="battery",
        resource_id=res_id_2,
        details="Swapped battery"
    )
    
    # Log 3: Transaction Resource (Different user)
    AuditService.log_action(
        db=session,
        user_id=None, # System action
        action="process_payment",
        resource_type="transaction",
        resource_id="tx_123",
        details="Payment processed"
    )
    
    # 3. Test Filter by Resource Type
    resp = client.get(f"{settings.API_V1_STR}/audit/data-access?resource_type=battery", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    assert all(l["resource_type"] == "battery" for l in data["logs"])
    assert any(l["resource_id"] == res_id_2 for l in data["logs"])
    
    # 4. Test Filter by Resource ID
    resp = client.get(f"{settings.API_V1_STR}/audit/data-access?resource_id={res_id_1}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 1
    assert any(l["resource_id"] == res_id_1 for l in data["logs"])
    
    # 5. Test Filter by Date Range
    # Assume logs are recent
    now = datetime.now(UTC)
    start = (now - timedelta(minutes=1)).isoformat()
    end = (now + timedelta(minutes=1)).isoformat()
    
    resp = client.get(f"{settings.API_V1_STR}/audit/data-access?start_date={start}&end_date={end}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] >= 3 # At least our 3 logs
    
    # 6. Test Filter by User ID
    resp = client.get(f"{settings.API_V1_STR}/audit/data-access?user_id={user.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # Should see user and battery logs, but not transaction (user_id=None)
    ids = [l["resource_id"] for l in data["logs"]]
    assert res_id_1 in ids
    assert res_id_2 in ids
    assert "tx_123" not in ids
