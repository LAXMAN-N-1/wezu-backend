import pytest
from fastapi import status

# --- POSITIVE CASES ---

def test_register_user_success(client):
    """Test successful user registration"""
    email = "newuser@example.com"
    response = client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": email,
            "password": "StrongPassword123!",
            "full_name": "New User",
            "phone_number": "1234567890"
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == email
    assert "id" in data

def test_login_user_success(client):
    """Test successful user login after registration"""
    email = "login_success@example.com"
    password = "Password123!"
    
    # Register
    client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Login Success User",
            "phone_number": "0987654321"
        },
    )
    
    # Login
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": email,
            "password": password
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

# --- NEGATIVE CASES ---

def test_register_duplicate_email(client):
    """Test registering with an existing email should fail"""
    email = "duplicate@example.com"
    payload = {
        "email": email,
        "password": "Password123!",
        "full_name": "User 1",
        "phone_number": "1112223334"
    }
    # First registration
    client.post("/api/v1/customer/auth/register", json=payload)
    
    # Second registration with same email
    response = client.post("/api/v1/customer/auth/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_login_invalid_credentials(client):
    """Test login with wrong password"""
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@test.com",
            "password": "wrong_password"
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

# --- EDGE CASES ---

def test_register_invalid_email_format(client):
    """Test registration with malformed email"""
    response = client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": "not-an-email",
            "password": "Password123!",
            "full_name": "Bad Email",
            "phone_number": "0000000000"
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_login_empty_payload(client):
    """Test login with missing fields"""
    response = client.post("/api/v1/auth/token", data={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
