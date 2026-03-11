def test_register_user(client):
    response = client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": "test@example.com",
            "password": "Password123!",
            "full_name": "Test User",
            "phone_number": "9876543210"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_login_user(client):
    # Register first
    client.post(
        "/api/v1/customer/auth/register",
        json={
            "email": "login@example.com",
            "password": "Password123!",
            "full_name": "Login User",
             "phone_number": "9998887776"
        },
    )
    
    # Login
    response = client.post(
        "/api/v1/customer/auth/token",
        data={
            "username": "login@example.com",
            "password": "Password123!"
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
