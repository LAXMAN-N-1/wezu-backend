import pytest
from datetime import datetime, UTC, timedelta
import json
from sqlmodel import Session, select

from app.models.user import User
from app.models.roles import RoleEnum
from app.models.rbac import Role, UserRole
from app.models.dealer import DealerProfile
from app.models.dealer_promotion import DealerPromotion, PromotionUsage
from app.models.station import Station


# ─── Fixtures ───

@pytest.fixture
def dealer_promo_env(session: Session):
    """Create dealer user, DealerProfile, station, and user."""
    # Roles
    dealer_role = session.exec(select(Role).where(Role.name == RoleEnum.DEALER.value)).first()
    if not dealer_role:
        dealer_role = Role(name=RoleEnum.DEALER.value)
        session.add(dealer_role)

    admin_role = session.exec(select(Role).where(Role.name == RoleEnum.ADMIN.value)).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.value)
        session.add(admin_role)
    session.commit()

    # Dealer user
    dealer_user = User(
        email="promo_dealer@test.com", hashed_password="pw",
        is_active=True, status="active",
    )
    session.add(dealer_user)
    session.commit()
    session.refresh(dealer_user)
    session.add(UserRole(user_id=dealer_user.id, role_id=dealer_role.id))

    # Admin user
    admin_user = User(
        email="promo_admin@test.com", hashed_password="pw",
        is_active=True, is_superuser=True, status="active",
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)
    session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))

    # Customer user
    customer_user = User(
        email="promo_cust@test.com", hashed_password="pw",
        is_active=True, status="active",
    )
    session.add(customer_user)
    session.commit()
    session.refresh(customer_user)

    # Dealer profile
    dealer_profile = DealerProfile(
        user_id=dealer_user.id,
        business_name="Promo Dealer Co",
        contact_person="Jane",
        contact_email="jane@test.com",
        contact_phone="9876543211",
        address_line1="456 Promo St",
        city="Delhi",
        state="Delhi",
        pincode="110001",
    )
    session.add(dealer_profile)
    session.commit()
    session.refresh(dealer_profile)

    # Station
    station1 = Station(
        name="Station A", address="A1", latitude=28.61, longitude=77.20,
        dealer_id=dealer_profile.id, total_slots=5, rating=4.5, status="active",
    )
    station2 = Station(
        name="Station B", address="B1", latitude=28.62, longitude=77.21,
        dealer_id=dealer_profile.id, total_slots=5, rating=4.0, status="active",
    )
    session.add_all([station1, station2])
    session.commit()
    session.refresh(station1)
    session.refresh(station2)

    return {
        "dealer_user": dealer_user,
        "admin_user": admin_user,
        "customer": customer_user,
        "dealer_profile": dealer_profile,
        "station1": station1,
        "station2": station2
    }


def get_token(user: User):
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


# ─── CRUD ───

class TestCampaignCRUD:
    def test_create_campaign(self, client, session, dealer_promo_env):
        """#1: Campaign created with all fields."""
        headers = get_token(dealer_promo_env["dealer_user"])
        payload = {
            "name": "Summer Sale",
            "promo_code": "SUMMER10",
            "discount_type": "PERCENTAGE",
            "discount_value": 10.0,
            "min_purchase_amount": 50.0,
            "budget_limit": 1000.0,
            "daily_cap": 50,
            "usage_limit_total": 500,
            "usage_limit_per_user": 2,
            "applicable_station_ids": [dealer_promo_env["station1"].id],
            "start_date": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "end_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        }
        resp = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"]
        assert data["name"] == "Summer Sale"
        assert data["total_discount_given"] == 0.0

    def test_list_campaigns(self, client, session, dealer_promo_env):
        """#2: Dealer sees own campaigns."""
        headers = get_token(dealer_promo_env["dealer_user"])
        # Needs at least one to list - rely on previous test
        resp = client.get("/api/v1/dealer-campaigns", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_campaign(self, client, session, dealer_promo_env):
        """#3: Single campaign returned."""
        headers = get_token(dealer_promo_env["dealer_user"])
        # Create one first
        payload = {
            "name": "Single Get test",
            "promo_code": "GETME",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": 5.0,
            "start_date": datetime.now(UTC).isoformat(),
            "end_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        }
        create_resp = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload)
        c_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/dealer-campaigns/{c_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["promo_code"] == "GETME"

    def test_update_campaign(self, client, session, dealer_promo_env):
        """#4: Fields updated correctly."""
        headers = get_token(dealer_promo_env["dealer_user"])
        payload = {
            "name": "Update test",
            "promo_code": "UPDATE",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": 5.0,
            "start_date": datetime.now(UTC).isoformat(),
            "end_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        }
        create_resp = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload)
        c_id = create_resp.json()["id"]

        resp = client.put(f"/api/v1/dealer-campaigns/{c_id}", headers=headers, json={"discount_value": 20.0})
        assert resp.status_code == 200
        assert resp.json()["discount_value"] == 20.0

    def test_deactivate_campaign(self, client, session, dealer_promo_env):
        """#5: is_active set to False."""
        headers = get_token(dealer_promo_env["dealer_user"])
        payload = {
            "name": "Deactivate test",
            "promo_code": "DEACT",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": 5.0,
            "start_date": datetime.now(UTC).isoformat(),
            "end_date": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        }
        create_resp = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload)
        c_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/dealer-campaigns/{c_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


# ─── Validation ───

class TestCampaignValidation:
    
    @pytest.fixture(autouse=True)
    def setup_promo(self, client, dealer_promo_env):
        headers = get_token(dealer_promo_env["dealer_user"])
        payload = {
            "name": "Validation Promo",
            "promo_code": "VALID10",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": 10.0,
            "min_purchase_amount": 50.0,
            "budget_limit": 20.0, # Enough for 2 uses
            "usage_limit_per_user": 2,
            "applicable_station_ids": [dealer_promo_env["station1"].id],
            "start_date": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "end_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        }
        resp = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload)
        self.promo_id = resp.json()["id"]
        
        # Expired promo
        payload_exp = payload.copy()
        payload_exp["promo_code"] = "EXPIRED"
        payload_exp["start_date"] = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        payload_exp["end_date"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        client.post("/api/v1/dealer-campaigns", headers=headers, json=payload_exp)

    def test_validate_valid_code(self, client, session, dealer_promo_env):
        """#6: Checkout validation succeeds."""
        headers = get_token(dealer_promo_env["customer"])
        resp = client.post(
            "/api/v1/dealer-campaigns/validate",
            headers=headers,
            json={"code": "VALID10", "order_amount": 100.0, "station_id": dealer_promo_env["station1"].id}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["discount_applied"] == 10.0
        assert data["final_amount"] == 90.0

    def test_validate_expired_code(self, client, session, dealer_promo_env):
        """#7: Expired code rejected."""
        headers = get_token(dealer_promo_env["customer"])
        resp = client.post(
            "/api/v1/dealer-campaigns/validate",
            headers=headers,
            json={"code": "EXPIRED", "order_amount": 100.0}
        )
        assert resp.status_code == 400
        assert "expired" in resp.json()["error"].lower()

    def test_validate_min_order(self, client, session, dealer_promo_env):
        """#9: Below minimum rejected."""
        headers = get_token(dealer_promo_env["customer"])
        resp = client.post(
            "/api/v1/dealer-campaigns/validate",
            headers=headers,
            json={"code": "VALID10", "order_amount": 30.0, "station_id": dealer_promo_env["station1"].id}
        )
        assert resp.status_code == 400
        assert "Minimum order" in resp.json()["error"]

    def test_validate_budget_exceeded(self, client, session, dealer_promo_env):
        """#10: Budget cap enforced."""
        headers = get_token(dealer_promo_env["customer"])
        
        # We need to test the budget directly through the service since Validation endpoint doesn't APPLY
        from app.services.campaign_service import CampaignService
        
        # Apply twice (budget is 20, discount is 10)
        CampaignService.apply_promo(session, self.promo_id, dealer_promo_env["customer"].id, 100, 10, 90)
        CampaignService.apply_promo(session, self.promo_id, dealer_promo_env["admin_user"].id, 100, 10, 90)
        
        # Third validation should fail because total_discount_given is now 20 (budget_limit)
        resp = client.post(
            "/api/v1/dealer-campaigns/validate",
            headers=headers,
            json={"code": "VALID10", "order_amount": 100.0, "station_id": dealer_promo_env["station1"].id}
        )
        assert resp.status_code == 400
        assert "budget exhausted" in resp.json()["error"].lower()

    def test_validate_usage_limit(self, client, session, dealer_promo_env):
        """#8: Over-limit per user rejected."""
        headers = get_token(dealer_promo_env["customer"])
        
        # Setup a new promo just for usage limit (so budget isn't hit)
        dealer_headers = get_token(dealer_promo_env["dealer_user"])
        payload = {
            "name": "Limit Promo", "promo_code": "LIMIT2",
            "discount_type": "FIXED_AMOUNT", "discount_value": 1.0,
            "usage_limit_per_user": 1,
            "start_date": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "end_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        }
        resp = client.post("/api/v1/dealer-campaigns", headers=dealer_headers, json=payload)
        limit_promo_id = resp.json()["id"]

        from app.services.campaign_service import CampaignService
        # Use it once
        CampaignService.apply_promo(session, limit_promo_id, dealer_promo_env["customer"].id, 100, 1, 99)
        
        # Validate second time should fail
        resp = client.post(
            "/api/v1/dealer-campaigns/validate",
            headers=headers,
            json={"code": "LIMIT2", "order_amount": 100.0}
        )
        assert resp.status_code == 400
        assert "usage limit" in resp.json()["error"].lower()


# ─── Analytics & Bulk Operations ───

class TestAnalyticsAndBulk:
    def test_campaign_analytics(self, client, session, dealer_promo_env):
        """#11: Usage count + totals returned."""
        headers = get_token(dealer_promo_env["dealer_user"])
        payload = {
            "name": "Analytics Promo", "promo_code": "ANALYTICS",
            "discount_type": "PERCENTAGE", "discount_value": 10.0,
            "start_date": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "end_date": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        }
        create_resp = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload)
        c_id = create_resp.json()["id"]

        from app.services.campaign_service import CampaignService
        # Record impression
        CampaignService.record_impression(session, c_id)
        # Apply
        CampaignService.apply_promo(session, c_id, dealer_promo_env["customer"].id, 100, 10, 90)

        resp = client.get(f"/api/v1/dealer-campaigns/{c_id}/analytics", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["impressions"] == 1
        assert data["usage_count"] == 1
        assert data["total_discount_given"] == 10.0
        assert data["additional_revenue_driven"] == 90.0

    def test_bulk_create_csv(self, client, session, dealer_promo_env):
        """#12: Multiple codes from CSV."""
        headers = get_token(dealer_promo_env["dealer_user"])
        csv_content = "name,promo_code,discount_type,discount_value\nBulk 1,BULK1,PERCENTAGE,10\nBulk 2,BULK2,FIXED_AMOUNT,50"
        
        files = {"file": ("promos.csv", csv_content.encode("utf-8"), "text/csv")}
        resp = client.post("/api/v1/dealer-campaigns/bulk-create", headers=headers, files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert len(data["errors"]) == 0

    def test_bulk_toggle(self, client, session, dealer_promo_env):
        """#13: Bulk activate/deactivate."""
        headers = get_token(dealer_promo_env["dealer_user"])
        payload1 = {
            "name": "Tog 1", "promo_code": "TOG1",
            "discount_type": "PERCENTAGE", "discount_value": 10.0,
            "start_date": datetime.now(UTC).isoformat(), "end_date": (datetime.now(UTC) + timedelta(days=30)).isoformat()
        }
        payload2 = {
            "name": "Tog 2", "promo_code": "TOG2",
            "discount_type": "PERCENTAGE", "discount_value": 10.0,
            "start_date": datetime.now(UTC).isoformat(), "end_date": (datetime.now(UTC) + timedelta(days=30)).isoformat()
        }
        id1 = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload1).json()["id"]
        id2 = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload2).json()["id"]

        resp = client.post(
            "/api/v1/dealer-campaigns/bulk-toggle",
            headers=headers,
            json={"campaign_ids": [id1, id2], "is_active": False}
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 2

    def test_clone_campaign(self, client, session, dealer_promo_env):
        """#14: Clone with new code."""
        headers = get_token(dealer_promo_env["dealer_user"])
        payload = {
            "name": "Original for Clone", "promo_code": "OCLONE",
            "discount_type": "PERCENTAGE", "discount_value": 10.0,
            "start_date": datetime.now(UTC).isoformat(), "end_date": (datetime.now(UTC) + timedelta(days=30)).isoformat()
        }
        c_id = client.post("/api/v1/dealer-campaigns", headers=headers, json=payload).json()["id"]

        resp = client.post(
            f"/api/v1/dealer-campaigns/{c_id}/clone",
            headers=headers,
            json={"new_promo_code": "NCLONE"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["promo_code"] == "NCLONE"
        assert "Copy" in data["name"]
        assert data["is_active"] is False # Clones are inactive by default


# ─── RBAC ───

class TestRBAC:
    def test_non_dealer_denied(self, client, session, dealer_promo_env):
        """#15: Non-dealer gets 403."""
        headers = get_token(dealer_promo_env["admin_user"])
        resp = client.get("/api/v1/dealer-campaigns", headers=headers)
        assert resp.status_code == 403
