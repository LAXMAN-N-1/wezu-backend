import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import datetime, timedelta

from app.models.commission import CommissionConfig, CommissionTier, CommissionLog
from app.models.settlement import Settlement
from app.models.chargeback import Chargeback
from app.models.settlement_dispute import SettlementDispute
from app.models.roles import RoleEnum
from app.models.user import User
from app.models.rbac import Role, UserRole


# ─── Fixtures ───

@pytest.fixture
def mock_users_and_roles(session: Session):
    roles = {}
    for r_name in [RoleEnum.ADMIN.value, RoleEnum.DEALER.value, RoleEnum.DRIVER.value, RoleEnum.CUSTOMER.value]:
        role = session.exec(select(Role).where(Role.name == r_name)).first()
        if not role:
            role = Role(name=r_name)
            session.add(role)
        roles[r_name] = role
    session.commit()

    users_data = {
        RoleEnum.ADMIN.value: User(email="admin_comm@test.com", hashed_password="pw", is_active=True),
        RoleEnum.DEALER.value: User(email="dealer_comm@test.com", hashed_password="pw", is_active=True),
        RoleEnum.DRIVER.value: User(email="driver_comm@test.com", hashed_password="pw", is_active=True),
        RoleEnum.CUSTOMER.value: User(email="customer_comm@test.com", hashed_password="pw", is_active=True),
    }

    for r_name, user in users_data.items():
        session.add(user)
        session.commit()
        session.refresh(user)
        link = UserRole(user_id=user.id, role_id=roles[r_name].id)
        session.add(link)
    session.commit()

    return users_data


def get_override_token(user: User):
    from app.core.security import create_access_token
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


# ─── Tests ───

class TestCommissionRates:
    """Tests 1-4: Commission rate configuration."""

    def test_create_commission_rate_flat(self, client, session, mock_users_and_roles):
        """#1: Admin can create a flat-fee commission config."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        headers = get_override_token(admin)
        data = {
            "transaction_type": "swap",
            "flat_fee": 25.0,
            "percentage": 0.0,
        }
        resp = client.post("/api/v1/dealer-commission/commission/rates", headers=headers, json=data)
        assert resp.status_code == 200
        body = resp.json()
        assert body["flat_fee"] == 25.0
        assert body["transaction_type"] == "swap"

    def test_create_commission_rate_percentage(self, client, session, mock_users_and_roles):
        """#2: Admin can create a percentage-based config."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        headers = get_override_token(admin)
        data = {
            "transaction_type": "rental",
            "percentage": 10.0,
            "flat_fee": 0.0,
        }
        resp = client.post("/api/v1/dealer-commission/commission/rates", headers=headers, json=data)
        assert resp.status_code == 200
        assert resp.json()["percentage"] == 10.0

    def test_create_tiered_commission(self, client, session, mock_users_and_roles):
        """#3: Admin can attach volume tiers to a config."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        headers = get_override_token(admin)
        data = {
            "transaction_type": "swap",
            "percentage": 5.0,
            "tiers": [
                {"min_volume": 0, "max_volume": 100, "percentage": 5.0, "flat_fee": 0},
                {"min_volume": 101, "max_volume": 500, "percentage": 3.0, "flat_fee": 0},
                {"min_volume": 501, "max_volume": None, "percentage": 1.5, "flat_fee": 0},
            ],
        }
        resp = client.post("/api/v1/dealer-commission/commission/rates", headers=headers, json=data)
        assert resp.status_code == 200
        config_id = resp.json()["id"]

        # Verify tiers were stored
        tiers = session.exec(
            select(CommissionTier).where(CommissionTier.config_id == config_id)
        ).all()
        assert len(tiers) == 3

    def test_effective_date_filtering(self, client, session, mock_users_and_roles):
        """#4: Only configs within effective date range apply."""
        from app.services.commission_service import CommissionService

        # Create a config effective in the past (expired)
        past_config = CommissionConfig(
            transaction_type="swap",
            percentage=99.0,
            effective_from=datetime(2020, 1, 1),
            effective_until=datetime(2020, 12, 31),
            is_active=True,
        )
        session.add(past_config)

        # Create a currently effective config
        current_config = CommissionConfig(
            transaction_type="swap",
            percentage=8.0,
            effective_from=datetime(2025, 1, 1),
            effective_until=None,
            is_active=True,
        )
        session.add(current_config)
        session.commit()

        rate = CommissionService.get_applicable_rate(session, "swap")
        # Should pick the current one, not the expired one
        assert rate["percentage"] == 8.0


class TestTieredRateResolution:
    """Tests 5-6: Volume-based tier selection."""

    def test_tiered_rate_selection_low_volume(self, client, session, mock_users_and_roles):
        """#5: Low-volume dealer gets correct tier rate."""
        from app.services.commission_service import CommissionService

        config = CommissionConfig(
            transaction_type="swap",
            percentage=5.0,
            effective_from=datetime(2025, 1, 1),
            is_active=True,
        )
        session.add(config)
        session.commit()
        session.refresh(config)

        session.add(CommissionTier(config_id=config.id, min_volume=0, max_volume=100, percentage=5.0))
        session.add(CommissionTier(config_id=config.id, min_volume=101, max_volume=500, percentage=3.0))
        session.commit()

        rate = CommissionService.get_applicable_rate(session, "swap", monthly_volume=50)
        assert rate["percentage"] == 5.0

    def test_tiered_rate_selection_high_volume(self, client, session, mock_users_and_roles):
        """#6: High-volume dealer gets discounted tier rate."""
        from app.services.commission_service import CommissionService

        config = CommissionConfig(
            transaction_type="swap",
            percentage=5.0,
            effective_from=datetime(2025, 1, 1),
            is_active=True,
        )
        session.add(config)
        session.commit()
        session.refresh(config)

        session.add(CommissionTier(config_id=config.id, min_volume=0, max_volume=100, percentage=5.0))
        session.add(CommissionTier(config_id=config.id, min_volume=101, max_volume=500, percentage=3.0))
        session.commit()

        rate = CommissionService.get_applicable_rate(session, "swap", monthly_volume=200)
        assert rate["percentage"] == 3.0


class TestSettlementGeneration:
    """Tests 7-9: Settlement creation accuracy."""

    def test_settlement_generation_accuracy(self, client, session, mock_users_and_roles):
        """#7: Settlement total matches manual sum, rounded to 2dp."""
        from app.services.settlement_service import SettlementService
        from app.models.financial import Transaction

        dealer = mock_users_and_roles[RoleEnum.DEALER.value]

        # Create commission logs
        for amt in [10.333, 20.667, 5.123]:
            log = CommissionLog(
                transaction_id=1,
                dealer_id=dealer.id,
                amount=amt,
                status="pending",
                created_at=datetime(2025, 2, 15),
            )
            session.add(log)
        session.commit()

        settlement = SettlementService.generate_monthly_settlement(session, dealer.id, "2025-02")
        expected = round(10.333 + 20.667 + 5.123, 2)
        assert settlement.total_commission == expected
        assert settlement.net_payable == expected  # No chargebacks

    def test_chargeback_deduction(self, client, session, mock_users_and_roles):
        """#8: Chargebacks are subtracted from settlement."""
        from app.services.settlement_service import SettlementService

        dealer = mock_users_and_roles[RoleEnum.DEALER.value]

        # Commission
        session.add(CommissionLog(
            transaction_id=1, dealer_id=dealer.id, amount=100.0,
            status="pending", created_at=datetime(2025, 3, 10),
        ))
        # Chargeback
        session.add(Chargeback(
            dealer_id=dealer.id, amount=15.50, reason="customer_refund",
            status="pending", created_at=datetime(2025, 3, 12),
        ))
        session.commit()

        settlement = SettlementService.generate_monthly_settlement(session, dealer.id, "2025-03")
        assert settlement.total_commission == 100.0
        assert settlement.chargeback_amount == 15.50
        assert settlement.net_payable == 84.50

    def test_settlement_available_by_2nd(self, client, session, mock_users_and_roles):
        """#9: Settlement created_at is a valid timestamp (simulating availability)."""
        from app.services.settlement_service import SettlementService

        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        session.add(CommissionLog(
            transaction_id=1, dealer_id=dealer.id, amount=50.0,
            status="pending", created_at=datetime(2025, 4, 15),
        ))
        session.commit()

        settlement = SettlementService.generate_monthly_settlement(session, dealer.id, "2025-04")
        assert settlement.created_at is not None
        assert settlement.status == "generated"


class TestBatchPayment:
    """Test 10: Batch processing."""

    def test_batch_payment_marks_paid(self, client, session, mock_users_and_roles):
        """#10: Batch payment updates status + sets paid_at."""
        from app.services.settlement_service import SettlementService

        settlement = Settlement(
            dealer_id=1,
            settlement_month="2025-01",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
            total_commission=100.0,
            net_payable=85.0,
            status="generated",
        )
        session.add(settlement)
        session.commit()

        result = SettlementService.process_batch_payments(session, "2025-01")
        assert result["processed"] == 1

        session.refresh(settlement)
        assert settlement.status == "paid"
        assert settlement.paid_at is not None
        assert settlement.transaction_reference is not None


class TestDealerDashboard:
    """Tests 11-13: Dealer dashboard and detail."""

    def test_dealer_dashboard_current_month(self, client, session, mock_users_and_roles):
        """#11: Dashboard returns current month earnings."""
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)

        # Add pending commission for current month
        now = datetime.utcnow()
        session.add(CommissionLog(
            transaction_id=1, dealer_id=dealer.id, amount=75.0,
            status="pending", created_at=now,
        ))
        session.commit()

        resp = client.get("/api/v1/dealer-commission/dealer/dashboard", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_month_earnings"] == 75.0

    def test_dealer_dashboard_12_month_history(self, client, session, mock_users_and_roles):
        """#12: Dashboard returns rolling 12-month array."""
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)

        # Use recent months (within last 12 months from now)
        now = datetime.utcnow()
        for i in range(3):
            month_offset = i + 1
            if now.month - month_offset > 0:
                m = now.month - month_offset
                y = now.year
            else:
                m = now.month - month_offset + 12
                y = now.year - 1
            month_str = f"{y}-{m:02d}"
            session.add(Settlement(
                dealer_id=dealer.id,
                settlement_month=month_str,
                start_date=datetime(y, m, 1),
                end_date=datetime(y, m, 28),
                total_commission=100.0 * (i+1),
                net_payable=90.0 * (i+1),
                status="paid",
            ))
        session.commit()

        resp = client.get("/api/v1/dealer-commission/dealer/dashboard", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["history"]) == 3

    def test_transaction_detail_line_items(self, client, session, mock_users_and_roles):
        """#13: Detail endpoint returns individual records."""
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)

        settlement = Settlement(
            dealer_id=dealer.id,
            settlement_month="2025-05",
            start_date=datetime(2025, 5, 1),
            end_date=datetime(2025, 5, 31),
            total_commission=200.0,
            net_payable=180.0,
            status="generated",
        )
        session.add(settlement)
        session.commit()
        session.refresh(settlement)

        # Link commission logs
        for i in range(3):
            session.add(CommissionLog(
                transaction_id=i+1, dealer_id=dealer.id, amount=66.67,
                status="processing", settlement_id=settlement.id,
                created_at=datetime(2025, 5, 10),
            ))
        session.commit()

        resp = client.get(
            f"/api/v1/dealer-commission/dealer/settlements/{settlement.id}/details",
            headers=headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["commission_items"]) == 3


class TestSettlementPDF:
    """Test 14: PDF generation."""

    def test_settlement_pdf_generation(self, client, session, mock_users_and_roles):
        """#14: PDF endpoint returns a file response."""
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)

        settlement = Settlement(
            dealer_id=dealer.id,
            settlement_month="2025-06",
            start_date=datetime(2025, 6, 1),
            end_date=datetime(2025, 6, 30),
            total_commission=500.0,
            net_payable=450.0,
            status="paid",
        )
        session.add(settlement)
        session.commit()
        session.refresh(settlement)

        resp = client.get(
            f"/api/v1/dealer-commission/dealer/settlements/{settlement.id}/pdf",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "application/pdf"


class TestDisputeWorkflow:
    """Tests 15-17: Dispute creation and resolution."""

    def test_dispute_creation(self, client, session, mock_users_and_roles):
        """#15: Dealer can open a dispute on a settlement."""
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)

        settlement = Settlement(
            dealer_id=dealer.id,
            settlement_month="2025-07",
            start_date=datetime(2025, 7, 1),
            end_date=datetime(2025, 7, 31),
            total_commission=300.0,
            net_payable=270.0,
            status="generated",
        )
        session.add(settlement)
        session.commit()
        session.refresh(settlement)

        resp = client.post(
            f"/api/v1/dealer-commission/dealer/settlements/{settlement.id}/dispute",
            headers=headers,
            json={"reason": "Missing 5 swap transactions"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"

    def test_dispute_resolution_approved(self, client, session, mock_users_and_roles):
        """#16: Admin upholds dispute → settlement adjusted."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]

        settlement = Settlement(
            dealer_id=dealer.id,
            settlement_month="2025-08",
            start_date=datetime(2025, 8, 1),
            end_date=datetime(2025, 8, 31),
            total_commission=400.0,
            net_payable=360.0,
            status="generated",
        )
        session.add(settlement)
        session.commit()
        session.refresh(settlement)

        dispute = SettlementDispute(
            settlement_id=settlement.id,
            dealer_id=dealer.id,
            reason="Incorrect rate applied",
            status="open",
        )
        session.add(dispute)
        session.commit()
        session.refresh(dispute)

        headers = get_override_token(admin)
        resp = client.post(
            f"/api/v1/dealer-commission/admin/disputes/{dispute.id}/resolve",
            headers=headers,
            json={"action": "approve", "notes": "Rate corrected", "adjustment_amount": 40.0},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

        session.refresh(settlement)
        assert settlement.net_payable == 400.0  # 360 + 40 adjustment

    def test_dispute_resolution_rejected(self, client, session, mock_users_and_roles):
        """#17: Admin rejects dispute → no change."""
        admin = mock_users_and_roles[RoleEnum.ADMIN.value]
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]

        settlement = Settlement(
            dealer_id=dealer.id,
            settlement_month="2025-09",
            start_date=datetime(2025, 9, 1),
            end_date=datetime(2025, 9, 30),
            total_commission=500.0,
            net_payable=450.0,
            status="generated",
        )
        session.add(settlement)
        session.commit()
        session.refresh(settlement)

        dispute = SettlementDispute(
            settlement_id=settlement.id,
            dealer_id=dealer.id,
            reason="Some complaint",
            status="open",
        )
        session.add(dispute)
        session.commit()
        session.refresh(dispute)

        headers = get_override_token(admin)
        resp = client.post(
            f"/api/v1/dealer-commission/admin/disputes/{dispute.id}/resolve",
            headers=headers,
            json={"action": "reject", "notes": "No evidence found", "adjustment_amount": 0.0},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        session.refresh(settlement)
        assert settlement.net_payable == 450.0  # Unchanged


class TestRateChanges:
    """Test 18: Rate change doesn't retroactively affect current month."""

    def test_rate_change_applies_next_period(self, client, session, mock_users_and_roles):
        """#18: Changed rate does not retroactively affect current month."""
        from app.services.commission_service import CommissionService

        # Old rate effective Jan-Feb
        session.add(CommissionConfig(
            transaction_type="swap", percentage=10.0,
            effective_from=datetime(2025, 1, 1),
            effective_until=datetime(2025, 2, 28),
            is_active=True,
        ))
        # New rate effective March onward
        session.add(CommissionConfig(
            transaction_type="swap", percentage=5.0,
            effective_from=datetime(2025, 3, 1),
            is_active=True,
        ))
        session.commit()

        # Query as of Feb 15 should get old rate
        rate_feb = CommissionService.get_applicable_rate(
            session, "swap", as_of_date=datetime(2025, 2, 15)
        )
        assert rate_feb["percentage"] == 10.0

        # Query as of March 15 should get new rate
        rate_mar = CommissionService.get_applicable_rate(
            session, "swap", as_of_date=datetime(2025, 3, 15)
        )
        assert rate_mar["percentage"] == 5.0


class TestRBACEnforcement:
    """Tests 19-20: Role-based access control."""

    def test_non_admin_cannot_set_rates(self, client, session, mock_users_and_roles):
        """#19: Dealer/Driver gets 403 on rate endpoints."""
        dealer = mock_users_and_roles[RoleEnum.DEALER.value]
        headers = get_override_token(dealer)
        data = {"transaction_type": "swap", "percentage": 5.0}
        resp = client.post("/api/v1/dealer-commission/commission/rates", headers=headers, json=data)
        assert resp.status_code == 403

    def test_non_dealer_cannot_access_dashboard(self, client, session, mock_users_and_roles):
        """#20: Admin/Driver gets 403 on dealer dashboard."""
        driver = mock_users_and_roles[RoleEnum.DRIVER.value]
        headers = get_override_token(driver)
        resp = client.get("/api/v1/dealer-commission/dealer/dashboard", headers=headers)
        assert resp.status_code == 403
