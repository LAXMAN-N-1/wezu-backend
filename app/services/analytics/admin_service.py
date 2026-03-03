from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.schemas.analytics.admin import AdminOverviewResponse
from .base import BaseAnalyticsService
from app.models.rental import Rental
from app.models.battery import Battery, BatteryStatus

class AnalyticsAdminService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d") -> AdminOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        
        # 1. Calculate MRR (Monthly Recurring Revenue via Rentals for now)
        target_date_ago = datetime.utcnow() - timedelta(days=days)
        previous_date_ago = datetime.utcnow() - timedelta(days=days * 2)
        
        current_mrr = db.query(func.sum(Rental.total_amount)).filter(Rental.created_at >= target_date_ago).scalar() or 0.0
        prev_mrr = db.query(func.sum(Rental.total_amount)).filter(Rental.created_at >= previous_date_ago, Rental.created_at < target_date_ago).scalar() or 0.0
        
        # 2. Risk - Alerts & Geo-breaches (Mocks mapping to IoT architecture)
        critical_batteries = db.query(func.count(Battery.id)).filter(Battery.health_status == "critical").scalar() or 0
        
        return AdminOverviewResponse(
            overview={
                "mrr": BaseAnalyticsService.format_kpi_card(current_mrr, current_mrr, prev_mrr),
                "revenue": BaseAnalyticsService.format_kpi_card(current_mrr * 0.8, current_mrr * 0.8, prev_mrr * 0.8) # Net calculation proxy
            },
            financials={
                "monthly_trend": [
                    {"x": target_date_ago.strftime("%Y-%m-%d"), "y": prev_mrr},
                    {"x": datetime.utcnow().strftime("%Y-%m-%d"), "y": current_mrr}
                ]
            },
            risk={
                "critical_alerts": critical_batteries,
                "geo_breaches": []
            },
            performance={
                "top_stations": [
                    # Real query: Group by Station ID to find highest volume
                    {"station_id": row[0], "swaps": row[1]} 
                    for row in db.query(Rental.start_station_id, func.count(Rental.id))
                    .filter(Rental.created_at >= target_date_ago)
                    .group_by(Rental.start_station_id)
                    .order_by(func.count(Rental.id).desc())
                    .limit(5).all()
                ],
                "avg_rental_duration_minutes": db.query(
                    func.avg(func.extract('epoch', Rental.completed_at - Rental.created_at) / 60)
                ).filter(Rental.created_at >= target_date_ago, Rental.completed_at.isnot(None)).scalar() or 0.0
            }
        )

analytics_admin_service = AnalyticsAdminService()
