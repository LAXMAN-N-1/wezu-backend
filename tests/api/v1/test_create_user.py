import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.models.user import User
from app.api import deps
from app.core.security import get_password_hash

def test_create_user_as_superuser(client: TestClient, session: Session):
    # 1. Create a superuser
    superuser = User(
        email="admin@example.com",
        phone_number="1234567890",
        full_name="Admin User",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=True
    )
    session.add(superuser)
    session.commit()
    session.refresh(superuser)
    
    # 2. Mock dependency for current user to be the superuser
    def get_superuser_override():
        return superuser
    
    from app.main import app
    app.dependency_overrides[deps.get_current_user] = get_superuser_override
    app.dependency_overrides[deps.get_current_user] = get_superuser_override

    # 3. Try to create a new user
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "newuser@example.com",
            "phone_number": "0987654321",
            "full_name": "New User",
            "password": "newpassword",
            "is_active": True
        }
    )
    
    # Assertions
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert "id" in data
    
    # Verify in DB
    user_in_db = session.query(User).filter(User.email == "newuser@example.com").first()
    assert user_in_db is not None
    assert user_in_db.full_name == "New User"
    
    # Clean up overrides
    app.dependency_overrides.clear()

def test_create_user_as_normal_user_fails(client: TestClient, session: Session):
    # 1. Create a normal user
    user = User(
        email="user@example.com",
        phone_number="1112223333",
        full_name="Normal User",
        hashed_password=get_password_hash("password"),
        is_active=True,
        is_superuser=False
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # 2. Mock dependency
    def get_user_override():
        return user
    
    from app.main import app
    app.dependency_overrides[deps.get_current_user] = get_user_override
    # We DON'T override get_current_active_superuser to test the failure
    
    # 3. Try to create a user
    response = client.post(
        "/api/v1/users/",
        json={
            "email": "another@example.com",
            "phone_number": "4445556666",
            "full_name": "Another User",
            "password": "password"
        }
    )
    
    # Assertions
    # Note: If we don't override get_current_active_superuser, it will call get_current_user (which is overridden)
    # and then check user.is_superuser. Since False, it should raise 400 or 403.
    # Actually deps.get_current_active_superuser calls get_current_user.
    
    assert response.status_code == 403
    # assert response.json()["error"] == "The user doesn't have enough privileges" # Detail might vary
    
    app.dependency_overrides.clear()
