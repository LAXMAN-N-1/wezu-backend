from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.schemas.analytics.dealer import DealerOverviewResponse
from .base import BaseAnalyticsService
from app.models.kyc import KYCRecord
from app.models.battery import Battery, BatteryStatus
from app.models.station import Station
from app.models.rental import Rental

class AnalyticsDealerService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d", dealer_profile_id: int = None) -> DealerOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        target_date_ago = datetime.utcnow() - timedelta(days=days)
        
        # Mocking an ID if none is passed for now (in realities, passed from the route router via current_user mapping)
        
        # 1. Walk-in Conversion proxies via KYC records
        verified_kyc = db.query(func.count(KYCRecord.id)).filter(KYCRecord.status == "verified", KYCRecord.submitted_at >= target_date_ago).scalar() or 0
        total_kyc = db.query(func.count(KYCRecord.id)).filter(KYCRecord.submitted_at >= target_date_ago).scalar() or 1 # Avoid div zero
        conversion_rate = (verified_kyc / total_kyc) * 100
        
        # 2. Inventory - Available batteries at stations owned by dealer
        # If dealer_profile_id was present: db.query(Battery).join(Station).filter(Station.dealer_id == dealer_profile_id)...
        available_stock = db.query(func.count(Battery.id)).filter(Battery.status == BatteryStatus.AVAILABLE).scalar() or 0
        
        # 3. Period Revenue (Mocked structure mapped off Rentals in period)
        period_rev = db.query(func.sum(Rental.total_amount)).filter(Rental.created_at >= target_date_ago).scalar() or 0.0
        
        return DealerOverviewResponse(
            overview={
                "conversion": BaseAnalyticsService.format_kpi_card(round(conversion_rate, 1), conversion_rate, conversion_rate - 2.0)
            },
            inventory={"days_of_charge": available_stock}, # mapped for demo
            sales={"period_revenue": [{"x": target_date_ago.strftime("%Y-%m-%d"), "y": period_rev}]}
        )

analytics_dealer_service = AnalyticsDealerService()
