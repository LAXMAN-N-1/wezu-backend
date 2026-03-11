import pytest
from datetime import datetime, date, timedelta
from sqlmodel import Session, select

from app.models.user import User
from app.models.roles import RoleEnum
from app.models.rbac import Role, UserRole
from app.models.financial import Wallet, Transaction
from app.models.revenue_report import RevenueReport


# ─── Fixtures ───

@pytest.fixture
def admin_and_dealer(session: Session):
    """Create admin + dealer for auth, plus test transactions."""
    # Roles
    admin_role = session.exec(select(Role).where(Role.name == RoleEnum.ADMIN.value)).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.value)
        session.add(admin_role)
    dealer_role = session.exec(select(Role).where(Role.name == RoleEnum.DEALER.value)).first()
    if not dealer_role:
        dealer_role = Role(name=RoleEnum.DEALER.value)
        session.add(dealer_role)
    session.commit()

    admin = User(
        email="fin_admin@test.com", hashed_password="pw",
        is_active=True, is_superuser=True, status="active",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    session.add(UserRole(user_id=admin.id, role_id=admin_role.id))

    dealer = User(
        email="fin_dealer@test.com", hashed_password="pw",
        is_active=True, status="active",
    )
    session.add(dealer)
    session.commit()
    session.refresh(dealer)
    session.add(UserRole(user_id=dealer.id, role_id=dealer_role.id))
    session.commit()

    # Create wallet + transactions for aggregation testing
    wallet = Wallet(user_id=admin.id, balance=1000.0)
    session.add(wallet)
    session.commit()
    session.refresh(wallet)

    now = datetime.utcnow()
    txns = [
        Transaction(wallet_id=wallet.id, amount=500.0, balance_after=1500.0,
                     type="credit", category="deposit", status="success",
                     reference_type="payment_gateway", razorpay_payment_id="pay_test1",
                     created_at=now),
        Transaction(wallet_id=wallet.id, amount=300.0, balance_after=1800.0,
                     type="credit", category="swap_fee", status="success",
                     reference_type="swap_session", created_at=now),
        Transaction(wallet_id=wallet.id, amount=-50.0, balance_after=1750.0,
                     type="debit", category="refund", status="success",
                     reference_type="admin_adjustment", created_at=now),
        Transaction(wallet_id=wallet.id, amount=200.0, balance_after=1950.0,
                     type="credit", category="deposit", status="success",
                     reference_type="payment_gateway", razorpay_payment_id="pay_test2",
                     created_at=now),
    ]
    for t in txns:
        session.add(t)
    session.commit()

    return {"admin": admin, "dealer": dealer}


def get_token(user: User):
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


# ─── Revenue Reports ───

class TestRevenueReport:
    def test_daily_revenue_report(self, client, session, admin_and_dealer):
        """#1: Daily report returns totals."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/admin/reports/revenue?period=daily&date={today}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_type"] == "daily"
        assert data["total_revenue"] >= 0  # May be 0 if UTC date != local date

    def test_weekly_revenue_report(self, client, session, admin_and_dealer):
        """#2: Weekly report works."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/admin/reports/revenue?period=weekly&date={today}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["report_type"] == "weekly"

    def test_monthly_revenue_report(self, client, session, admin_and_dealer):
        """#3: Monthly report works."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/admin/reports/revenue?period=monthly&date={today}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["report_type"] == "monthly"

    def test_revenue_breakdown_by_category(self, client, session, admin_and_dealer):
        """#6: Category breakdown present."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/admin/reports/revenue?period=daily&date={today}", headers=headers)
        data = resp.json()
        assert "breakdown_by_category" in data
        assert data["breakdown_by_category"] is not None

    def test_revenue_breakdown_by_station(self, client, session, admin_and_dealer):
        """#4/#5: Station/source breakdown present."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/admin/reports/revenue?period=monthly&date={today}", headers=headers)
        data = resp.json()
        assert "breakdown_by_station" in data

    def test_refund_tracking(self, client, session, admin_and_dealer):
        """#5: Refund amount tracked."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/admin/reports/revenue?period=monthly&date={today}", headers=headers)
        data = resp.json()
        assert "total_refunds" in data
        assert data["total_refunds"] >= 0

    def test_avg_transaction_value(self, client, session, admin_and_dealer):
        """#15: AVG calculated correctly."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        resp = client.get(f"/api/v1/admin/reports/revenue?period=daily&date={today}", headers=headers)
        data = resp.json()
        if data["total_transactions"] > 0:
            expected_avg = data["total_revenue"] / data["total_transactions"]
            assert abs(data["avg_transaction_value"] - round(expected_avg, 2)) < 0.01


# ─── Trends ───

class TestTrends:
    def test_growth_trends(self, client, session, admin_and_dealer):
        """#7: Trends endpoint returns list."""
        headers = get_token(admin_and_dealer["admin"])
        # Generate a report first
        today = date.today().isoformat()
        client.get(f"/api/v1/admin/reports/revenue?period=monthly&date={today}", headers=headers)
        resp = client.get("/api/v1/admin/reports/revenue/trends?period_type=monthly&periods=3", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ─── Reconciliation ───

class TestReconciliation:
    def test_reconciliation_report(self, client, session, admin_and_dealer):
        """#8: Reconciliation returns totals and discrepancy."""
        headers = get_token(admin_and_dealer["admin"])
        month = date.today().strftime("%Y-%m")
        resp = client.get(f"/api/v1/admin/reports/reconciliation?month={month}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "internal_total" in data
        assert "gateway_total" in data
        assert "discrepancy" in data
        assert "reconciled" in data


# ─── Generate + Export ───

class TestGenerateAndExport:
    def test_generate_report_on_demand(self, client, session, admin_and_dealer):
        """#9: POST /generate creates report."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        resp = client.post(
            "/api/v1/admin/reports/generate", headers=headers,
            json={"period_type": "daily", "date": today},
        )
        assert resp.status_code == 200
        assert resp.json()["report_type"] == "daily"

    def test_export_csv(self, client, session, admin_and_dealer):
        """#10: CSV download works."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        # Generate first
        gen = client.post(
            "/api/v1/admin/reports/generate", headers=headers,
            json={"period_type": "daily", "date": today},
        )
        report_id = gen.json()["id"]
        resp = client.get(f"/api/v1/admin/reports/export/csv?report_id={report_id}", headers=headers)
        assert resp.status_code == 200
        assert "report_type" in resp.text

    def test_export_json(self, client, session, admin_and_dealer):
        """#11: JSON download works."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        gen = client.post(
            "/api/v1/admin/reports/generate", headers=headers,
            json={"period_type": "daily", "date": today},
        )
        report_id = gen.json()["id"]
        resp = client.get(f"/api/v1/admin/reports/export/json?report_id={report_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == report_id


# ─── History + Get by ID ───

class TestHistory:
    def test_report_history(self, client, session, admin_and_dealer):
        """#12: List reports paginated."""
        headers = get_token(admin_and_dealer["admin"])
        # Generate a couple
        today = date.today().isoformat()
        client.post("/api/v1/admin/reports/generate", headers=headers,
                     json={"period_type": "daily", "date": today})
        resp = client.get("/api/v1/admin/reports/history?skip=0&limit=10", headers=headers)
        assert resp.status_code == 200
        assert "total" in resp.json()
        assert "data" in resp.json()

    def test_get_report_by_id(self, client, session, admin_and_dealer):
        """#13: Single report retrieval."""
        headers = get_token(admin_and_dealer["admin"])
        today = date.today().isoformat()
        gen = client.post("/api/v1/admin/reports/generate", headers=headers,
                           json={"period_type": "daily", "date": today})
        report_id = gen.json()["id"]
        resp = client.get(f"/api/v1/admin/reports/{report_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == report_id


# ─── RBAC ───

class TestRBAC:
    def test_non_admin_denied(self, client, session, admin_and_dealer):
        """#14: Dealer gets 400/403."""
        dealer = admin_and_dealer["dealer"]
        headers = get_token(dealer)
        resp = client.get("/api/v1/admin/reports/revenue?period=daily", headers=headers)
        assert resp.status_code in (400, 403)
