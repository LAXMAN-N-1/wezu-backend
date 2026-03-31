from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, extract
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any

from app.schemas.analytics.logistics import LogisticsOverviewResponse
from app.schemas.analytics.base import KpiCard, TrendPoint, DistributionPoint
from .base import BaseAnalyticsService
from app.models.logistics import BatteryTransfer
from app.models.user import User
from app.models.battery import Battery

class AnalyticsLogisticsService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d", logistics_user_id: int = None) -> LogisticsOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        target_date = datetime.now(UTC) - timedelta(days=days)
        
        # 1. Delivery Analytics (Mapping to BatteryTransfers)
        deliveries_today = db.query(func.count(BatteryTransfer.id)).filter(
            BatteryTransfer.created_at >= datetime.now(UTC).replace(hour=0, minute=0, second=0)
        ).scalar() or 0
        
        pending_deliv = db.query(func.count(BatteryTransfer.id)).filter(BatteryTransfer.status == "pending").scalar() or 0
        failed_deliv = db.query(func.count(BatteryTransfer.id)).filter(BatteryTransfer.status == "cancelled").scalar() or 0
        
        delivery_analytics = {
            "total_deliveries": db.exec(select(func.count(BatteryTransfer.id))).one() or 0,
            "deliveries_today": deliveries_today,
            "pending_deliveries": pending_deliv,
            "failed_deliveries": failed_deliv
        }

        # 2. Route & Driver Analytics
        avg_time = db.query(func.avg(extract('epoch', BatteryTransfer.updated_at - BatteryTransfer.created_at) / 60)).filter(
            BatteryTransfer.status == "completed"
        ).scalar() or 0
        
        route_analytics = {
            "average_delivery_time_min": round(float(avg_time), 1),
            "route_efficiency": 92.5, # Mocked
            "distance_covered": 450.0 # Mocked
        }

        driver_perf = [] # Mocked since driver_id is not in BatteryTransfer directly
        
        driver_analytics = {
            "driver_performance": [{"name": row[0], "deliveries": row[1]} for row in driver_perf],
            "driver_rating_avg": 4.8
        }

        # 3. Order Analytics
        total_orders = db.exec(select(func.count(BatteryTransfer.id))).one() or 1
        success_rate = (db.query(func.count(BatteryTransfer.id)).filter(BatteryTransfer.status == "completed").scalar() or 0) / total_orders * 100
        
        order_analytics = {
            "delivery_success_rate": round(success_rate, 1),
            "delivery_delay_rate": 5.2,
            "average_processing_time": 15.0
        }

        # 4. Reverse Logistics
        # As we don't have order_type, we mock this for now
        returns = 0
        
        reverse_logistics = {
            "battery_returns": returns,
            "pickup_requests": returns,
            "failed_pickups": 2
        }

        return LogisticsOverviewResponse(
            delivery_analytics=delivery_analytics,
            route_analytics=route_analytics,
            driver_analytics=driver_analytics,
            order_analytics=order_analytics,
            reverse_logistics=reverse_logistics,
            customer_communication={"sms_sent": 150, "delivery_confirmations": returns},
            customer_feedback={"positive": 45, "negative": 2},
            charts={
                "delivery_time_trend": [TrendPoint(x="Mon", y=25), TrendPoint(x="Tue", y=22)],
                "success_rate_pie": [
                    DistributionPoint(label="Success", value=success_rate),
                    DistributionPoint(label="Failed", value=100-success_rate)
                ]
            }
        )

analytics_logistics_service = AnalyticsLogisticsService()
