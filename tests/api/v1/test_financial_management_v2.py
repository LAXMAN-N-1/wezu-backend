import pytest
from datetime import datetime, date, timedelta
from sqlmodel import Session, select
from app.models.user import User, UserType, UserStatus
from app.models.dealer import DealerProfile
from app.models.battery import Battery, BatteryStatus
from app.models.financial import Transaction, TransactionType, TransactionStatus
from app.models.revenue_report import RevenueReport
from app.models.settlement import Settlement
from app.core.security import create_access_token

@pytest.fixture
def test_data(session: Session):
    # 1. Create Admin
    admin = User(
        email="admin_test@wezu.com",
        phone_number="1111111111",
        user_type=UserType.ADMIN,
        status=UserStatus.ACTIVE,
        is_superuser=True,
        hashed_password="pw"
    )
    session.add(admin)
    
    # 2. Create Dealer
    dealer_user = User(
        email="dealer_test@wezu.com",
        phone_number="2222222222",
        user_type=UserType.DEALER,
        status=UserStatus.ACTIVE,
        hashed_password="pw"
    )
    session.add(dealer_user)
    session.commit()
    session.refresh(dealer_user)
    
    # Check if a dealer role exists, if not create it
    from app.models.rbac import Role
    dealer_role = session.exec(select(Role).where(Role.name == "dealer")).first()
    if not dealer_role:
        dealer_role = Role(name="dealer", slug="dealer")
        session.add(dealer_role)
        session.commit()
        session.refresh(dealer_role)
    
    dealer_profile = DealerProfile(user_id=dealer_user.id, business_name="Test Dealer", is_active=True)
    session.add(dealer_profile)
    
    # 3. Create Batteries with costs for margin analysis
    battery1 = Battery(
        serial_number="BATT001",
        purchase_cost=50000.0,
        battery_type="48V/30Ah",
        status=BatteryStatus.AVAILABLE
    )
    session.add(battery1)
    
    # 4. Create historical revenue reports for forecasting
    today = date.today()
    for i in range(1, 4):
        start = today - timedelta(days=30*i)
        report = RevenueReport(
            report_type="monthly",
            period_start=start,
            period_end=start + timedelta(days=29),
            total_revenue=10000.0 * i,  # Increasing revenue
            net_revenue=9000.0 * i,
            total_transactions=100 * i,
            breakdown_by_source={"rental": 8000.0 * i, "purchase": 2000.0 * i}
        )
        session.add(report)
    
    session.commit()
    return {
        "admin": admin,
        "dealer_user": dealer_user,
        "dealer_profile": dealer_profile,
        "battery": battery1
    }

def get_auth_header(user_id: int):
    from app.core.security import create_access_token
    token = create_access_token(subject=str(user_id))
    return {"Authorization": f"Bearer {token}"}

class TestFinancialManagementV2:
    
    def test_revenue_forecast_admin(self, client, session, test_data):
        """Test admin revenue forecast endpoint."""
        headers = get_auth_header(test_data["admin"].id)
        resp = client.get("/api/v1/admin_financial_reports/revenue/forecast?period=monthly", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "forecasted_revenue" in data
        assert data["forecasted_revenue"] > 0
        assert data["confidence"] == "medium"  # Since we added 3 reports

    def test_dealer_profitability_analysis(self, client, session, test_data):
        """Test dealer profitability analysis logic."""
        from app.models.station import Station
        station = Station(name="Test Station", dealer_id=test_data["dealer_profile"].id, latitude=0, longitude=0)
        session.add(station)
        session.commit()
        session.refresh(station)
        
        test_data["battery"].station_id = station.id
        session.add(test_data["battery"])
        session.commit()
        
        headers = get_auth_header(test_data["dealer_user"].id)
        resp = client.get("/api/v1/dealer_analytics/profitability", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "revenue" in data
        assert "estimated_costs" in data
        assert data["estimated_costs"]["depreciation"] > 0
        assert "margin_percentage" in data

    def test_margin_by_battery_type(self, client, session, test_data):
        """Test margin breakdown by battery type."""
        from app.models.station import Station
        station = Station(name="Test Station 2", dealer_id=test_data["dealer_profile"].id, latitude=0, longitude=0)
        session.add(station)
        session.commit()
        session.refresh(station)
        
        test_data["battery"].station_id = station.id
        session.add(test_data["battery"])
        session.commit()

        headers = get_auth_header(test_data["dealer_user"].id)
        resp = client.get("/api/v1/dealer_analytics/margin-by-battery", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert data[0]["battery_type"] == "48V/30Ah"
        assert data[0]["asset_value"] == 50000.0

    def test_settlement_due_date_automation(self, client, session, test_data):
        """Verify that settlement generation sets a due date."""
        from app.services.settlement_service import SettlementService
        
        month = "2026-03"
        settlement = SettlementService.generate_monthly_settlement(
            session, test_data["dealer_user"].id, month
        )
        
        assert settlement.due_date is not None
        assert settlement.due_date.day == 10
        assert settlement.due_date.month == 4

    def test_revenue_source_breakdown(self, client, session, test_data):
        """Verify that periodic reports include source breakdown."""
        from app.services.financial_report_service import FinancialReportService
        
        txn = Transaction(
            user_id=test_data["dealer_user"].id,
            amount=100.0,
            transaction_type=TransactionType.RENTAL_PAYMENT,
            status=TransactionStatus.SUCCESS
        )
        session.add(txn)
        session.commit()
        
        report = FinancialReportService.generate_periodic_report(
            session, "daily", date.today()
        )
        
        assert "breakdown_by_source" in report.model_dump()
        assert report.breakdown_by_source["rental"] == 100.0
