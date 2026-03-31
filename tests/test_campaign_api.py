"""
Integration Tests for Campaign API Endpoints
Tests the admin campaign CRUD endpoints using FastAPI TestClient
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models.user import User, UserStatus
from app.models.campaign import Campaign, CampaignStatus, CampaignType
from app.api import deps


# ── Fixtures ──

@pytest.fixture
def admin_user(session: Session) -> User:
    user = User(
        phone_number="8888800000",
        email="apiadmin@wezu.com",
        full_name="API Admin",
        status=UserStatus.ACTIVE,
        is_superuser=True,
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def non_admin_user(session: Session) -> User:
    user = User(
        phone_number="8888800001",
        email="normaluser@wezu.com",
        full_name="Normal User",
        status=UserStatus.ACTIVE,
        is_superuser=False,
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def auth_client(client: TestClient, admin_user: User):
    """Client with admin auth dependency overridden."""
    def override_superuser():
        return admin_user

    from app.main import app
    app.dependency_overrides[deps.get_current_active_superuser] = override_superuser
    app.dependency_overrides[deps.get_current_user] = override_superuser
    yield client
    app.dependency_overrides.pop(deps.get_current_active_superuser, None)
    app.dependency_overrides.pop(deps.get_current_user, None)


@pytest.fixture
def non_auth_client(client: TestClient, non_admin_user: User):
    """Client with non-admin user (superuser check will fail)."""
    def override_user():
        return non_admin_user

    from app.main import app
    app.dependency_overrides[deps.get_current_user] = override_user
    # Don't override get_current_active_superuser so it raises
    yield client
    app.dependency_overrides.pop(deps.get_current_user, None)


CAMPAIGN_BASE_URL = "/api/v1/admin/campaigns"


def _campaign_payload(**overrides):
    """Default campaign creation payload."""
    data = {
        "name": "Integration Test Campaign",
        "type": "manual",
        "message_title": "Test Title",
        "message_body": "Test body message",
        "frequency_cap": 3,
        "target_criteria": {},
        "targets": [],
    }
    data.update(overrides)
    return data


# ── Tests ──

class TestCreateCampaignEndpoint:
    def test_create_campaign_endpoint(self, auth_client: TestClient):
        response = auth_client.post(CAMPAIGN_BASE_URL + "/", json=_campaign_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Integration Test Campaign"
        assert data["status"] == "draft"
        assert data["sent_count"] == 0

    def test_create_campaign_with_targets(self, auth_client: TestClient):
        payload = _campaign_payload(
            targets=[
                {"rule_type": "location", "rule_config": {"city": "Delhi"}},
            ]
        )
        response = auth_client.post(CAMPAIGN_BASE_URL + "/", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["targets"]) == 1


class TestListCampaignsEndpoint:
    def test_list_campaigns_pagination(self, auth_client: TestClient):
        # Create 3 campaigns
        for i in range(3):
            auth_client.post(
                CAMPAIGN_BASE_URL + "/",
                json=_campaign_payload(name=f"Camp {i}"),
            )
        response = auth_client.get(CAMPAIGN_BASE_URL + "/", params={"skip": 0, "limit": 2})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_campaigns_status_filter(self, auth_client: TestClient):
        auth_client.post(CAMPAIGN_BASE_URL + "/", json=_campaign_payload(name="Draft 1"))

        response = auth_client.get(CAMPAIGN_BASE_URL + "/", params={"status": "draft"})
        assert response.status_code == 200
        data = response.json()
        assert all(c["status"] == "draft" for c in data)

        # No active campaigns
        response = auth_client.get(CAMPAIGN_BASE_URL + "/", params={"status": "active"})
        assert response.status_code == 200
        assert len(response.json()) == 0


class TestGetCampaignEndpoint:
    def test_get_campaign_detail(self, auth_client: TestClient):
        create_resp = auth_client.post(CAMPAIGN_BASE_URL + "/", json=_campaign_payload())
        campaign_id = create_resp.json()["id"]

        response = auth_client.get(f"{CAMPAIGN_BASE_URL}/{campaign_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == campaign_id
        assert data["name"] == "Integration Test Campaign"


class TestUpdateCampaignEndpoint:
    def test_update_campaign_endpoint(self, auth_client: TestClient):
        create_resp = auth_client.post(CAMPAIGN_BASE_URL + "/", json=_campaign_payload())
        campaign_id = create_resp.json()["id"]

        response = auth_client.put(
            f"{CAMPAIGN_BASE_URL}/{campaign_id}",
            json={"name": "Updated Name", "message_title": "New Title"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["message_title"] == "New Title"


class TestDeleteCampaignEndpoint:
    def test_delete_campaign_endpoint(self, auth_client: TestClient):
        create_resp = auth_client.post(CAMPAIGN_BASE_URL + "/", json=_campaign_payload())
        campaign_id = create_resp.json()["id"]

        response = auth_client.delete(f"{CAMPAIGN_BASE_URL}/{campaign_id}")
        assert response.status_code == 200

        # Verify it's gone
        get_resp = auth_client.get(f"{CAMPAIGN_BASE_URL}/{campaign_id}")
        assert get_resp.status_code == 404

    def test_delete_active_campaign_fails(self, auth_client: TestClient, session: Session):
        # Create and activate a campaign
        create_resp = auth_client.post(
            CAMPAIGN_BASE_URL + "/",
            json=_campaign_payload(
                type="birthday",
            ),
        )
        campaign_id = create_resp.json()["id"]

        # Activate it
        auth_client.post(f"{CAMPAIGN_BASE_URL}/{campaign_id}/activate")

        # Try to delete — should fail
        response = auth_client.delete(f"{CAMPAIGN_BASE_URL}/{campaign_id}")
        assert response.status_code == 400


class TestActivateCampaignEndpoint:
    def test_activate_campaign_endpoint(self, auth_client: TestClient):
        scheduled_time = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        create_resp = auth_client.post(
            CAMPAIGN_BASE_URL + "/",
            json=_campaign_payload(scheduled_at=scheduled_time),
        )
        campaign_id = create_resp.json()["id"]

        response = auth_client.post(f"{CAMPAIGN_BASE_URL}/{campaign_id}/activate")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "scheduled"


class TestAnalyticsEndpoint:
    def test_analytics_endpoint(self, auth_client: TestClient):
        create_resp = auth_client.post(CAMPAIGN_BASE_URL + "/", json=_campaign_payload())
        campaign_id = create_resp.json()["id"]

        response = auth_client.get(f"{CAMPAIGN_BASE_URL}/{campaign_id}/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["campaign_id"] == campaign_id
        assert "sent_count" in data
        assert "open_rate" in data
        assert "conversion_rate" in data


class TestTestSendEndpoint:
    def test_test_send_endpoint(self, auth_client: TestClient):
        create_resp = auth_client.post(CAMPAIGN_BASE_URL + "/", json=_campaign_payload())
        campaign_id = create_resp.json()["id"]

        response = auth_client.post(f"{CAMPAIGN_BASE_URL}/{campaign_id}/test")
        assert response.status_code == 200
        data = response.json()
        assert "test" in data["message"].lower()


class TestUnauthorizedAccess:
    def test_unauthorized_access(self, non_auth_client: TestClient):
        """Non-superuser should be blocked by get_current_active_superuser."""
        response = non_auth_client.post(CAMPAIGN_BASE_URL + "/", json=_campaign_payload())
        # Should be 400 (user doesn't have enough privileges) or 403
        assert response.status_code in (400, 403, 401)
