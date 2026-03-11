import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select, func
from app.api import deps
from app.models.admin_user import AdminUser
from app.models.rbac import Role, UserRole
from app.models.user import User

def create_superuser_bulk(session):
    user = session.exec(select(AdminUser).where(AdminUser.email == "admin@bulk.com")).first()
    if user:
        return user
    user = AdminUser(phone_number='2658997906', 
        email="admin@bulk.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def test_bulk_role_assign(client: TestClient, session: Session):
    admin = create_superuser_bulk(session)
    
    # Setup Users
    u1 = User(phone_number='3341369027', email="bulk1@test.com", is_active=True)
    u2 = User(phone_number='2958179346', email="bulk2@test.com", is_active=True)
    session.add(u1)
    session.add(u2)
    session.commit()
    
    # Setup Role
    role = Role(name="Bulk Role", is_active=True)
    session.add(role)
    session.commit()
    
    app = client.app
    app.dependency_overrides[deps.get_current_active_superuser] = lambda: admin
    
    # Action: Assign to u1, u2 and a non-existent u999
    payload = {
        "role_id": role.id,
        "user_ids": [u1.id, u2.id, 99999]
    }
    
    resp = client.post("/api/v1/admin/rbac/roles/bulk-assign", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["total_requested"] == 3
    assert data["total_success"] == 2
    assert data["total_failed"] == 1
    
    # Verify results
    r1 = next(r for r in data["results"] if r["user_id"] == u1.id)
    assert r1["success"] is True
    
    r3 = next(r for r in data["results"] if r["user_id"] == 99999)
    assert r3["success"] is False
    assert "not found" in r3["message"].lower()
    
    # Verify DB
    count = session.exec(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)).one()
    assert count == 2
