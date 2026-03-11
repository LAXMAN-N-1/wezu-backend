from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, extract
from datetime import datetime, timedelta
from typing import Dict, Any

from app.schemas.analytics.admin import AdminOverviewResponse
from app.schemas.analytics.base import KpiCard, TrendPoint, DistributionPoint
from .base import BaseAnalyticsService
from app.models.user import User
from app.models.rbac import UserRole
from app.models.rental import Rental
from app.utils.constants import RentalStatus, BatteryStatus
from app.models.battery import Battery
from app.models.station import Station
from app.models.dealer import DealerProfile
from app.models.logistics import BatteryTransfer
from app.models.support import SupportTicket
from app.utils.constants import PaymentStatus

class AnalyticsAdminService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d") -> AdminOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        target_date = datetime.utcnow() - timedelta(days=days)
        prev_target_date = datetime.utcnow() - timedelta(days=days * 2)

        # Helper for KPI cards
        def get_kpi(current_val, prev_val):
            trend = ((current_val - prev_val) / prev_val * 100) if prev_val != 0 else 0
            status = "up" if trend >= 0 else "down"
            return KpiCard(value=float(current_val), trend_percentage=round(trend, 2), status=status)

        # 1. Platform Overview
        # Assuming customers don't have a specific role_id or use UserRole.USER
        from app.utils.constants import UserRole
        from app.models.rbac import UserRole as UserRoleTable, Role
        
        # Approximate: Users that are just regular users
        total_users = db.query(func.count(User.id)).scalar() or 0
        active_users_24h = db.query(func.count(User.id)).filter(User.last_login >= datetime.utcnow() - timedelta(hours=24)).scalar() or 0
        total_dealers = db.query(func.count(DealerProfile.id)).scalar() or 0
        
        # Approximate: logistics users (if we don't have UserType, maybe count drivers or skip exact count)
        total_logistics = 0  # To be refined if Logistics has a specific role
        
        total_stations = db.query(func.count(Station.id)).scalar() or 0
        total_batteries = db.query(func.count(Battery.id)).scalar() or 0

        platform_overview = {
            "total_users": get_kpi(total_users, total_users), # Simple count for now
            "active_users_24h": get_kpi(active_users_24h, active_users_24h),
            "total_dealers": get_kpi(total_dealers, total_dealers),
            "total_logistics": get_kpi(total_logistics, total_logistics),
            "total_stations": get_kpi(total_stations, total_stations),
            "total_batteries": get_kpi(total_batteries, total_batteries)
        }

        # 2. Rental Analytics
        rentals_today = db.query(func.count(Rental.id)).filter(Rental.start_time >= datetime.utcnow().replace(hour=0, minute=0, second=0)).scalar() or 0
        rentals_week = db.query(func.count(Rental.id)).filter(Rental.start_time >= datetime.utcnow() - timedelta(days=7)).scalar() or 0
        avg_duration = db.query(func.avg(extract('epoch', Rental.end_time - Rental.start_time) / 3600)).filter(Rental.status == RentalStatus.COMPLETED).scalar() or 0
        
        rental_analytics = {
            "rentals_today": rentals_today,
            "rentals_this_week": rentals_week,
            "avg_rental_duration_hours": round(float(avg_duration), 2),
            "battery_utilization_rate": 85.0 # Mocked for now
        }

        # 3. Financial Overview
        total_rev_today = db.query(func.sum(Rental.total_price)).filter(Rental.start_time >= datetime.utcnow().replace(hour=0, minute=0, second=0)).scalar() or 0
        total_rev_month = db.query(func.sum(Rental.total_price)).filter(Rental.start_time >= datetime.utcnow().replace(day=1)).scalar() or 0
        revenue_rentals = db.query(func.sum(Rental.total_price)).filter(Rental.start_time >= target_date).scalar() or 0
        
        revenue_analytics = {
            "total_revenue_today": float(total_rev_today),
            "total_revenue_month": float(total_rev_month),
            "revenue_from_rentals": float(revenue_rentals),
            "commission_paid_dealers": float(revenue_rentals * 0.1) # Assuming 10%
        }

        # 4. Battery & Fleet
        health_90_100 = db.query(func.count(Battery.id)).filter(Battery.health_percentage >= 90).scalar() or 0
        health_80_90 = db.query(func.count(Battery.id)).filter(and_(Battery.health_percentage >= 80, Battery.health_percentage < 90)).scalar() or 0
        health_below_80 = db.query(func.count(Battery.id)).filter(Battery.health_percentage < 80).scalar() or 0

        battery_fleet_analytics = {
            "total_batteries": total_batteries,
            "batteries_in_use": db.query(func.count(Battery.id)).filter(Battery.status == BatteryStatus.RENTED).scalar() or 0,
            "health_distribution": {
                "90-100%": health_90_100,
                "80-90%": health_80_90,
                "<80%": health_below_80
            }
        }

        # 5. Station Analytics
        top_stations = db.query(Station.name, func.count(Rental.id)).join(Rental, Station.id == Rental.pickup_station_id).group_by(Station.name).order_by(desc(func.count(Rental.id))).limit(5).all()
        
        station_analytics = {
            "top_performing_stations": [{"name": row[0], "rentals": row[1]} for row in top_stations],
            "avg_rentals_per_station": round(total_batteries / total_stations if total_stations > 0 else 0, 2)
        }

        # 6. Financial & Operational
        pending_tickets = db.query(func.count(SupportTicket.id)).filter(SupportTicket.status == "open").scalar() or 0
        
        financial_analytics = {
            "daily_revenue": float(revenue_rentals / days if days > 0 else 0),
            "monthly_growth_rate": 12.5 # Mocked
        }
        
        operational_analytics = {
            "support_tickets": total_users, # placeholder for total tickets
            "pending_issues": pending_tickets,
            "system_uptime": 99.9
        }

        return AdminOverviewResponse(
            platform_overview=platform_overview,
            rental_analytics=rental_analytics,
            revenue_analytics=revenue_analytics,
            battery_fleet_analytics=battery_fleet_analytics,
            station_analytics=station_analytics,
            customer_analytics={}, # To be refined
            financial_analytics=financial_analytics,
            operational_analytics=operational_analytics,
            charts={
                "revenue_trend": [TrendPoint(x=(datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d"), y=1000 + i*50) for i in range(days)],
                "battery_health": [
                    DistributionPoint(label="90-100%", value=health_90_100),
                    DistributionPoint(label="80-90%", value=health_80_90),
                    DistributionPoint(label="<80%", value=health_below_80)
                ]
            }
        )

analytics_admin_service = AnalyticsAdminService()
