import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.models.user import User
from app.models.driver_profile import DriverProfile
from app.models.rbac import Role
import traceback

def test_driver_onboarding_flow(client: TestClient, session: Session):
    print("\nStarting test_driver_onboarding_flow")
    try:
        # 1. Register a new user
        email = "test_driver_onboarding@example.com"
        password = "password123"
        payload = {
            "email": email,
            "password": password,
            "full_name": "Test Driver",
            "phone_number": "9876543210"
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 200
        user_data = response.json()
        user_id = user_data["id"]

        # 2. Login to get token
        login_payload = {
            "username": email,
            "password": password
        }
        response = client.post("/api/v1/auth/login", data=login_payload)
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Onboard as Driver
        onboard_data = {
            "license_number": "DL-1234567890",
            "vehicle_type": "scooter",
            "vehicle_plate": "MH-12-AB-1234"
        }
        response = client.post("/api/v1/drivers/onboard", json=onboard_data, headers=headers)
        if response.status_code != 200:
            print(f"Onboard failed: {response.json()}")
        assert response.status_code == 200
        profile_data = response.json()["data"]
        assert profile_data["user_id"] == user_id
        assert profile_data["license_number"] == onboard_data["license_number"]

        # 4. Verify Role Assignment
        # Reload user from DB to check roles
        user = session.get(User, user_id)
        role_names = [r.name for r in user.roles]
        assert "driver" in role_names

        # 5. Get Driver Profile via /me
        response = client.get("/api/v1/drivers/me", headers=headers)
        assert response.status_code == 200
        fetched_profile = response.json()["data"]
        assert fetched_profile["id"] == profile_data["id"]
        assert fetched_profile["license_number"] == onboard_data["license_number"]
        
    except Exception:
        traceback.print_exc()
        raise
