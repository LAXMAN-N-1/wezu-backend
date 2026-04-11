import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.rbac import Role
from app.core.config import settings
from fastapi.testclient import TestClient
import io


def get_admin_auth_headers(client: TestClient, email: str = "bulk_import_admin@test.com"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Bulk Import Admin",
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


def test_bulk_import_users(client, session: Session):
    """Test POST /admin/users/bulk-import with valid CSV."""
    email = "bulk_test_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    # Ensure admin
    user = session.exec(select(User).where(User.email == email)).first()
    user.is_superuser = True
    session.add(user)
    session.commit()
    
    # Create CSV content
    csv_content = """email,full_name,phone_number,password,roles
bulkuser1@test.com,Bulk User One,1234567890,TestPass123!,
bulkuser2@test.com,Bulk User Two,0987654321,TestPass456!,
"""
    
    # Upload CSV
    resp = client.post(
        f"{settings.API_V1_STR}/admin/users/bulk-import",
        files={"file": ("users.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    
    # Check response
    assert data["success_count"] == 2
    assert data["failure_count"] == 0
    assert data["total_rows"] == 2
    assert len(data["imported_users"]) == 2
    assert data["notifications_sent"] == 2


def test_bulk_import_validates_csv(client, session: Session):
    """Test bulk import validates CSV format."""
    email = "bulk_validate_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    user = session.exec(select(User).where(User.email == email)).first()
    user.is_superuser = True
    session.add(user)
    session.commit()
    
    # CSV missing required columns
    csv_content = """email,name
test@test.com,Test User
"""
    
    resp = client.post(
        f"{settings.API_V1_STR}/admin/users/bulk-import",
        files={"file": ("users.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers
    )
    assert resp.status_code == 400
    assert "must have columns" in resp.json()["error"]


def test_bulk_import_handles_errors(client, session: Session):
    """Test bulk import handles row-level errors."""
    email = "bulk_error_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    user = session.exec(select(User).where(User.email == email)).first()
    user.is_superuser = True
    session.add(user)
    session.commit()
    
    # CSV with invalid data
    csv_content = """email,full_name,phone_number
,Missing Email,1234567890
invalid-email,No At Sign,1234567890
valid@test.com,Valid User,1234567890
"""
    
    resp = client.post(
        f"{settings.API_V1_STR}/admin/users/bulk-import",
        files={"file": ("users.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    
    # Should have 1 success, 2 failures
    assert data["success_count"] == 1
    assert data["failure_count"] == 2
    assert len(data["errors"]) == 2


def test_bulk_status_update(client, session: Session):
    """Test POST /admin/users/bulk-status-update works."""
    email = "bulk_status_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    user = session.exec(select(User).where(User.email == email)).first()
    user.is_superuser = True
    session.add(user)
    session.commit()
    
    # Create test users
    target_emails = ["bulkstatus1@test.com", "bulkstatus2@test.com"]
    target_ids = []
    for target_email in target_emails:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": target_email,
                "password": "Password123!",
                "full_name": "Bulk Status Target",
                "phone_number": str(abs(hash(target_email)))[:10].ljust(10, '0')
            },
        )
        target = session.exec(select(User).where(User.email == target_email)).first()
        target_ids.append(target.id)
    
    # Bulk suspend
    resp = client.post(
        f"{settings.API_V1_STR}/admin/users/bulk-status-update",
        json={
            "user_ids": target_ids,
            "action": "suspend",
            "reason": "Seasonal suspension test"
        },
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == "suspend"
    assert data["success_count"] == 2
    assert data["failure_count"] == 0


def test_user_export_json(client, session: Session):
    """Test GET /admin/users/export returns JSON data."""
    email = "export_admin@test.com"
    headers = get_admin_auth_headers(client, email=email)
    
    user = session.exec(select(User).where(User.email == email)).first()
    user.is_superuser = True
    session.add(user)
    session.commit()
    
    # Export users
    resp = client.get(
        f"{settings.API_V1_STR}/admin/users/export?format=json",
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    
    # Check response structure
    assert "export_id" in data
    assert "format" in data
    assert data["format"] == "json"
    assert "total_users" in data
    assert "data" in data
    assert isinstance(data["data"], list)
