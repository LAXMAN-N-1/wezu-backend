from __future__ import annotations
from sqlmodel import Session, select, func, and_, desc, extract
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
from typing import Dict, Any

from app.schemas.analytics.admin import AdminOverviewResponse
from app.schemas.analytics.base import KpiCard, TrendPoint, DistributionPoint
from .base import BaseAnalyticsService
from app.models.user import User
from app.models.rbac import UserRole, Role
from app.models.rental import Rental
from app.utils.constants import RentalStatus, BatteryStatus
from app.models.battery import Battery
from app.models.station import Station
from app.models.dealer import DealerProfile
from app.models.logistics import BatteryTransfer
from app.models.support import SupportTicket

class AnalyticsAdminService(BaseAnalyticsService):
    @staticmethod
    async def get_overview(db: Session, period: str = "30d") -> AdminOverviewResponse:
        days = BaseAnalyticsService.parse_period(period)
        now = datetime.now(UTC)
        target_date = now - timedelta(days=days)
        prev_target_date = now - timedelta(days=days * 2)

        # Helper for KPI cards
        def get_kpi(current_val, prev_val):
            if prev_val != 0:
                trend = ((current_val - prev_val) / prev_val) * 100
            elif current_val > 0:
                trend = 100.0
            else:
                trend = 0.0
            status = "up" if trend >= 0 else "down"
            return KpiCard(value=float(current_val), trend_percentage=round(trend, 2), status=status)

        # 1. Platform Overview
        total_users = db.exec(select(func.count(User.id))).one() or 0
        prev_total_users = db.exec(select(func.count(User.id)).where(User.created_at < target_date)).one() or 0
        active_users_24h = db.exec(
            select(func.count(User.id)).where(User.last_login >= now - timedelta(hours=24))
        ).one() or 0
        total_dealers = db.exec(select(func.count(DealerProfile.id))).one() or 0
        prev_total_dealers = db.exec(
            select(func.count(DealerProfile.id)).where(DealerProfile.created_at < target_date)
        ).one() or 0

        total_logistics = db.exec(
            select(func.count(func.distinct(UserRole.user_id)))
            .join(Role, Role.id == UserRole.role_id)
            .where(
                func.lower(Role.name).like("%logistic%")
                | func.lower(Role.name).like("%warehouse%")
                | func.lower(Role.name).like("%driver%")
            )
        ).one() or 0

        total_stations = db.exec(select(func.count(Station.id))).one() or 0
        prev_total_stations = db.exec(
            select(func.count(Station.id)).where(Station.created_at < target_date)
        ).one() or 0
        total_batteries = db.exec(select(func.count(Battery.id))).one() or 0
        prev_total_batteries = db.exec(
            select(func.count(Battery.id)).where(Battery.created_at < target_date)
        ).one() or 0

        platform_overview = {
            "total_users": get_kpi(total_users, prev_total_users),
            "active_users_24h": get_kpi(active_users_24h, active_users_24h),
            "total_dealers": get_kpi(total_dealers, prev_total_dealers),
            "total_logistics": get_kpi(total_logistics, total_logistics),
            "total_stations": get_kpi(total_stations, prev_total_stations),
            "total_batteries": get_kpi(total_batteries, prev_total_batteries),
        }

        # 2. Rental Analytics
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        rentals_today = db.exec(
            select(func.count(Rental.id)).where(Rental.start_time >= today_start)
        ).one() or 0
        rentals_week = db.exec(
            select(func.count(Rental.id)).where(Rental.start_time >= now - timedelta(days=7))
        ).one() or 0
        avg_duration = db.exec(
            select(func.avg(extract('epoch', Rental.end_time - Rental.start_time) / 3600))
            .where(Rental.status == RentalStatus.COMPLETED)
        ).one() or 0
        batteries_in_use = db.exec(
            select(func.count(Battery.id)).where(Battery.status == BatteryStatus.RENTED)
        ).one() or 0
        battery_utilization_rate = (
            (float(batteries_in_use) / float(total_batteries)) * 100 if total_batteries > 0 else 0.0
        )

        rental_analytics = {
            "rentals_today": rentals_today,
            "rentals_this_week": rentals_week,
            "avg_rental_duration_hours": round(float(avg_duration), 2),
            "battery_utilization_rate": round(battery_utilization_rate, 2),
        }

        # 3. Financial Overview
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total_rev_today = db.exec(
            select(func.coalesce(func.sum(Rental.total_amount), 0.0))
            .where(Rental.start_time >= today_start)
        ).one() or 0
        total_rev_month = db.exec(
            select(func.coalesce(func.sum(Rental.total_amount), 0.0))
            .where(Rental.start_time >= month_start)
        ).one() or 0
        revenue_rentals = db.exec(select(func.sum(Rental.total_amount)).where(Rental.start_time >= target_date)).one() or 0
        commission_paid_dealers = 0.0
        try:
            from app.models.commission import CommissionLog

            commission_paid_dealers = db.exec(
                select(func.coalesce(func.sum(CommissionLog.amount), 0.0))
                .where(CommissionLog.created_at >= target_date)
            ).one() or 0.0
        except Exception:
            # Keep zero when commission table is unavailable in early environments.
            commission_paid_dealers = 0.0

        revenue_analytics = {
            "total_revenue_today": float(total_rev_today),
            "total_revenue_month": float(total_rev_month),
            "revenue_from_rentals": float(revenue_rentals),
            "commission_paid_dealers": float(commission_paid_dealers),
        }

        # 4. Battery & Fleet
        health_90_100 = db.exec(select(func.count(Battery.id)).where(Battery.health_percentage >= 90)).one() or 0
        health_80_90 = db.exec(select(func.count(Battery.id)).where(and_(Battery.health_percentage >= 80, Battery.health_percentage < 90))).one() or 0
        health_below_80 = db.exec(select(func.count(Battery.id)).where(Battery.health_percentage < 80)).one() or 0

        battery_fleet_analytics = {
            "total_batteries": total_batteries,
            "batteries_in_use": batteries_in_use,
            "health_distribution": {
                "90-100%": health_90_100,
                "80-90%": health_80_90,
                "<80%": health_below_80,
            },
        }

        # 5. Station Analytics
        top_stations = db.exec(
            select(Station.name, func.count(Rental.id))
            .join(Rental, Station.id == Rental.start_station_id)
            .group_by(Station.name)
            .order_by(desc(func.count(Rental.id)))
            .limit(5)
        ).all()
        total_period_rentals = db.exec(
            select(func.count(Rental.id)).where(Rental.start_time >= target_date)
        ).one() or 0

        station_analytics = {
            "top_performing_stations": [{"name": row[0], "rentals": row[1]} for row in top_stations],
            "avg_rentals_per_station": round(total_period_rentals / total_stations if total_stations > 0 else 0, 2),
        }

        # 6. Financial & Operational
        total_tickets = db.exec(select(func.count(SupportTicket.id))).one() or 0
        pending_tickets = db.exec(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open")).one() or 0

        prev_revenue = db.exec(
            select(func.coalesce(func.sum(Rental.total_amount), 0.0))
            .where(
                Rental.start_time >= prev_target_date,
                Rental.start_time < target_date,
            )
        ).one() or 0.0
        if float(prev_revenue) > 0:
            monthly_growth_rate = ((float(revenue_rentals) - float(prev_revenue)) / float(prev_revenue)) * 100
        elif float(revenue_rentals) > 0:
            monthly_growth_rate = 100.0
        else:
            monthly_growth_rate = 0.0

        transfers_in_period = db.exec(
            select(func.count(BatteryTransfer.id)).where(BatteryTransfer.created_at >= target_date)
        ).one() or 0
        successful_transfers = db.exec(
            select(func.count(BatteryTransfer.id))
            .where(
                BatteryTransfer.created_at >= target_date,
                BatteryTransfer.status.in_(["delivered", "received", "completed"]),
            )
        ).one() or 0
        system_uptime = (
            (float(successful_transfers) / float(transfers_in_period)) * 100
            if transfers_in_period > 0
            else 100.0
        )

        financial_analytics = {
            "daily_revenue": float(revenue_rentals / days if days > 0 else 0),
            "monthly_growth_rate": round(monthly_growth_rate, 2),
        }

        operational_analytics = {
            "support_tickets": total_tickets,
            "pending_issues": pending_tickets,
            "system_uptime": round(system_uptime, 2),
        }

        total_customers = db.exec(
            select(func.count(func.distinct(Rental.user_id)))
        ).one() or 0
        active_customers = db.exec(
            select(func.count(func.distinct(Rental.user_id))).where(Rental.start_time >= target_date)
        ).one() or 0
        customer_analytics = {
            "total_customers": int(total_customers),
            "active_customers": int(active_customers),
        }

        revenue_rows = db.exec(
            select(func.date(Rental.start_time), func.coalesce(func.sum(Rental.total_amount), 0.0))
            .where(Rental.start_time >= target_date)
            .group_by(func.date(Rental.start_time))
            .order_by(func.date(Rental.start_time))
        ).all()
        revenue_by_day: Dict[Any, float] = {}
        for day, amount in revenue_rows:
            normalized_day = datetime.fromisoformat(day).date() if isinstance(day, str) else day
            revenue_by_day[normalized_day] = float(amount or 0.0)

        revenue_trend = []
        first_day = target_date.date()
        for offset in range(days):
            current_day = first_day + timedelta(days=offset)
            revenue_trend.append(
                TrendPoint(
                    x=current_day.strftime("%Y-%m-%d"),
                    y=float(revenue_by_day.get(current_day, 0.0)),
                )
            )

        return AdminOverviewResponse(
            platform_overview=platform_overview,
            rental_analytics=rental_analytics,
            revenue_analytics=revenue_analytics,
            battery_fleet_analytics=battery_fleet_analytics,
            station_analytics=station_analytics,
            customer_analytics=customer_analytics,
            financial_analytics=financial_analytics,
            operational_analytics=operational_analytics,
            charts={
                "revenue_trend": revenue_trend,
                "battery_health": [
                    DistributionPoint(label="90-100%", value=health_90_100),
                    DistributionPoint(label="80-90%", value=health_80_90),
                    DistributionPoint(label="<80%", value=health_below_80),
                ],
            },
        )

analytics_admin_service = AnalyticsAdminService()
