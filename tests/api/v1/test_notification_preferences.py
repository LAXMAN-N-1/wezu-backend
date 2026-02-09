import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.core.config import settings
from fastapi.testclient import TestClient
import json


def get_auth_headers(client: TestClient, email: str = "notif_pref_user@test.com"):
    # 1. Register
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Notif Pref User",
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


def test_get_notification_preferences_defaults(client, session: Session):
    """Test GET returns default preferences for new user."""
    email = "notif_pref_test_get@test.com"
    headers = get_auth_headers(client, email=email)
    
    resp = client.get(f"{settings.API_V1_STR}/users/me/notification-preferences", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    
    # Check structure
    assert "email" in data
    assert "sms" in data
    assert "push" in data
    
    # Check default values
    assert data["email"]["rental_confirmations"] == True
    assert data["email"]["promotional"] == False
    assert data["sms"]["otp"] == True
    assert data["push"]["battery_available"] == True


def test_update_notification_preferences(client, session: Session):
    """Test PUT updates preferences correctly."""
    email = "notif_pref_test_update@test.com"
    headers = get_auth_headers(client, email=email)
    
    # 1. Update email promotional only
    resp = client.put(
        f"{settings.API_V1_STR}/users/me/notification-preferences",
        json={
            "email": {
                "promotional": True,
                "rental_confirmations": True,
                "payment_receipts": True,
                "security_alerts": True
            }
        },
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"]["promotional"] == True
    
    # 2. Verify persistence
    resp = client.get(f"{settings.API_V1_STR}/users/me/notification-preferences", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"]["promotional"] == True
    
    # 3. Update push preferences
    resp = client.put(
        f"{settings.API_V1_STR}/users/me/notification-preferences",
        json={
            "push": {
                "promotional": True,
                "battery_available": False,
                "payment_reminders": True
            }
        },
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["push"]["promotional"] == True
    assert data["push"]["battery_available"] == False
    # Email should still be persisted
    assert data["email"]["promotional"] == True


def test_partial_update_preserves_other_channels(client, session: Session):
    """Test that updating one channel doesn't affect others."""
    email = "notif_pref_test_partial@test.com"
    headers = get_auth_headers(client, email=email)
    
    # 1. Set initial state
    client.put(
        f"{settings.API_V1_STR}/users/me/notification-preferences",
        json={
            "email": {"promotional": True, "rental_confirmations": True, "payment_receipts": True, "security_alerts": True},
            "sms": {"otp": False, "rental_confirmations": True, "payment_receipts": True},
            "push": {"promotional": True, "battery_available": True, "payment_reminders": True}
        },
        headers=headers
    )
    
    # 2. Update only SMS
    resp = client.put(
        f"{settings.API_V1_STR}/users/me/notification-preferences",
        json={
            "sms": {"otp": True, "rental_confirmations": True, "payment_receipts": True}
        },
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    
    # SMS updated
    assert data["sms"]["otp"] == True
    
    # Others unchanged
    assert data["email"]["promotional"] == True
    assert data["push"]["promotional"] == True


def test_quiet_hours_configuration(client, session: Session):
    """Test quiet hours can be configured."""
    email = "notif_pref_test_quiet@test.com"
    headers = get_auth_headers(client, email=email)
    
    # 1. Check defaults
    resp = client.get(f"{settings.API_V1_STR}/users/me/notification-preferences", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "quiet_hours" in data
    assert data["quiet_hours"]["enabled"] == False
    assert data["quiet_hours"]["start_time"] == "22:00"
    assert data["quiet_hours"]["end_time"] == "07:00"
    
    # 2. Enable quiet hours with custom times
    resp = client.put(
        f"{settings.API_V1_STR}/users/me/notification-preferences",
        json={
            "quiet_hours": {
                "enabled": True,
                "start_time": "23:30",
                "end_time": "06:00",
                "timezone": "Asia/Kolkata"
            }
        },
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quiet_hours"]["enabled"] == True
    assert data["quiet_hours"]["start_time"] == "23:30"
    assert data["quiet_hours"]["end_time"] == "06:00"
    assert data["quiet_hours"]["timezone"] == "Asia/Kolkata"


def test_channel_master_toggles(client, session: Session):
    """Test channel-level enable/disable toggles."""
    email = "notif_pref_test_toggle@test.com"
    headers = get_auth_headers(client, email=email)
    
    # 1. Check defaults (all enabled)
    resp = client.get(f"{settings.API_V1_STR}/users/me/notification-preferences", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"]["enabled"] == True
    assert data["sms"]["enabled"] == True
    assert data["push"]["enabled"] == True
    
    # 2. Disable email channel
    resp = client.put(
        f"{settings.API_V1_STR}/users/me/notification-preferences",
        json={
            "email": {
                "enabled": False,
                "rental_confirmations": True,
                "payment_receipts": True,
                "promotional": False,
                "security_alerts": True
            }
        },
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"]["enabled"] == False
    # Other channels unchanged
    assert data["sms"]["enabled"] == True
    assert data["push"]["enabled"] == True
