import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.roles import RoleEnum
from app.models.rbac import Role, UserRole
from app.models.dealer import DealerProfile
from app.core.security import create_access_token

@pytest.fixture
def dealer_env(session: Session):
    """Setup a dealer user and profile."""
    # Dealer user
    dealer_user = User(
        email="dealer_settings@test.com", 
        hashed_password="$argon2id$v=19$m=65536,t=3,p=4$lSjZ3Y10w3Qp5SjZ3Y10w$F9T0+1b+8l2SjZ3Y10w", # Mock hash
        phone_number="9998887776",
        is_active=True, status="active",
        full_name="Dealer Setup"
    )
    session.add(dealer_user)
    session.commit()
    session.refresh(dealer_user)

    # Dealer profile
    dealer_profile = DealerProfile(
        user_id=dealer_user.id,
        business_name="Settings Dealer Co",
        contact_person="Settings Jane",
        contact_email="jane@test.com",
        contact_phone="9876543211",
        address_line1="456 Settings St",
        city="Delhi",
        state="Delhi",
        pincode="110001",
        bank_details={}
    )
    session.add(dealer_profile)
    session.commit()
    session.refresh(dealer_profile)

    token = create_access_token(subject=str(dealer_user.id))
    return {
        "user": dealer_user,
        "profile": dealer_profile,
        "headers": {"Authorization": f"Bearer {token}"}
    }


class TestDealerSettingsEndpoints:
    def test_verification_status(self, client, dealer_env):
        resp = client.get("/api/v1/dealer-portal/settings/verification-status", headers=dealer_env["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert "checklist" in data
        assert "progress_percentage" in data

    def test_change_email(self, client, dealer_env):
        resp = client.post("/api/v1/dealer-portal/settings/profile/change-email", 
            headers=dealer_env["headers"],
            json={"new_email": "new.email@test.com"}
        )
        assert resp.status_code == 200
        assert resp.json()["pending_email"] == "new.email@test.com"

    def test_notification_schedule(self, client, dealer_env):
        resp = client.put("/api/v1/dealer-portal/settings/notification-schedule", 
            headers=dealer_env["headers"],
            json={
                "quiet_hours_enabled": True,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
                "quiet_on_weekends": False
            }
        )
        assert resp.status_code == 200

    def test_test_notifications(self, client, dealer_env):
        resp = client.post("/api/v1/dealer-portal/settings/notifications/test", 
            headers=dealer_env["headers"],
            json={
                "channels": ["email", "sms"],
                "title": "A Test",
                "message": "Hello"
            }
        )
        assert resp.status_code == 200
        
    def test_notification_history(self, client, dealer_env):
        resp = client.get("/api/v1/dealer-portal/settings/notifications/history", headers=dealer_env["headers"])
        assert resp.status_code == 200
        # Since we just sent test notifications, there should be some
        assert len(resp.json()["history"]) > 0

    def test_session_timeout(self, client, dealer_env):
        resp = client.put("/api/v1/dealer-portal/settings/security/session-timeout", 
            headers=dealer_env["headers"],
            json={"timeout_minutes": 120}
        )
        assert resp.status_code == 200

    def test_export_data(self, client, dealer_env):
        resp = client.post("/api/v1/dealer-portal/settings/export-data", headers=dealer_env["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["dealer_profile"]["business_name"] == "Settings Dealer Co"
        assert data["user_profile"]["phone"] == "9998887776"
