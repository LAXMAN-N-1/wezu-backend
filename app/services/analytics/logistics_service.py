from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.schemas.analytics.logistics import LogisticsOverviewResponse
from .base import BaseAnalyticsService
from app.models.maintenance import MaintenanceRecord
from app.models.battery import Battery, BatteryHealth

class AnalyticsLogisticsService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d", logistics_user_id: int = None) -> LogisticsOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        target_date_ago = datetime.utcnow() - timedelta(days=days)
        
        # 1. MTTR Proxy (Counting total maintenance interventions performed in period)
        total_maintenance = db.query(func.count(MaintenanceRecord.id)).filter(MaintenanceRecord.status == "completed", MaintenanceRecord.performed_at >= target_date_ago).scalar() or 0
        
        # 2. Network Map - Surplus vs Depleted batteries across the network
        total_batteries = db.query(func.count(Battery.id)).scalar() or 1
        depleted_batteries = db.query(func.count(Battery.id)).filter(Battery.current_charge < 20).scalar() or 0
        
        # Depleted Percentage
        depleted_pct = (depleted_batteries / total_batteries) * 100
        
        return LogisticsOverviewResponse(
            overview={
                "mttr": BaseAnalyticsService.format_kpi_card(total_maintenance, total_maintenance, 0) # Mapping count as placeholder for MTTR minutes
            },
            slas={"transfer_times": []},
            network_map={
                "surplus": total_batteries - depleted_batteries,
                "depleted": depleted_batteries,
                "depleted_percentage": round(depleted_pct, 1)
            }
        )

analytics_logistics_service = AnalyticsLogisticsService()
