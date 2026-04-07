from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from sqlmodel import Session, select, func
from sqlalchemy import cast, Date, Integer, case
from datetime import datetime, timedelta, UTC
from app.api import deps
from app.core.config import settings
from app.utils.runtime_cache import cached_call

from app.models.user import User, UserStatus, KYCStatus
from app.models.financial import Transaction, TransactionStatus, TransactionType
from app.models.swap import SwapSession
from app.models.battery import Battery, BatteryHealth, BatteryStatus, LocationType
from app.models.station import Station, StationStatus

router = APIRouter()

def get_percentage_change(current: float, previous: float) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100.0, 1)

@router.get("/overview")
def get_analytics_overview(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        now = datetime.now(UTC)
        thirty_days_ago = now - timedelta(days=30)
        sixty_days_ago = now - timedelta(days=60)

        # Revenue current + previous in one query
        rev_row = db.exec(
            select(
                func.coalesce(func.sum(case(
                    (Transaction.created_at >= thirty_days_ago, Transaction.amount),
                    else_=0
                )), 0).label("current"),
                func.coalesce(func.sum(case(
                    (Transaction.created_at < thirty_days_ago, Transaction.amount),
                    else_=0
                )), 0).label("prev"),
            ).where(
                Transaction.status == TransactionStatus.SUCCESS,
                Transaction.created_at >= sixty_days_ago
            )
        ).one()
        rev_current = float(rev_row.current)
        rev_prev = float(rev_row.prev)

        # Active users total + those existing before 30d in one query
        user_row = db.exec(
            select(
                func.count(User.id).label("total"),
                func.coalesce(func.sum(case(
                    (User.created_at < thirty_days_ago, 1), else_=0
                )), 0).label("prev"),
            ).where(User.status == UserStatus.ACTIVE)
        ).one()
        users_total = user_row.total or 0
        users_prev = user_row.prev or 0

        # Swaps current + previous in one query
        swap_row = db.exec(
            select(
                func.coalesce(func.sum(case(
                    (SwapSession.created_at >= thirty_days_ago, 1), else_=0
                )), 0).label("current"),
                func.coalesce(func.sum(case(
                    (SwapSession.created_at < thirty_days_ago, 1), else_=0
                )), 0).label("prev"),
            ).where(SwapSession.created_at >= sixty_days_ago)
        ).one()
        swaps_current = swap_row.current or 0
        swaps_prev = swap_row.prev or 0

        # Battery utilization in one query
        bat_row = db.exec(
            select(
                func.count(Battery.id).label("total"),
                func.coalesce(func.sum(case(
                    (Battery.status == BatteryStatus.RENTED, 1), else_=0
                )), 0).label("rented"),
            )
        ).one()
        total_batteries = bat_row.total or 1
        rented_batteries = bat_row.rented or 0
        utilization = round((rented_batteries / total_batteries) * 100, 1)

        return {
            "revenue": {"total": rev_current, "growth": get_percentage_change(rev_current, rev_prev)},
            "active_users": {"total": users_total, "growth": get_percentage_change(users_total, users_prev)},
            "battery_swaps": {"total": swaps_current, "growth": get_percentage_change(swaps_current, swaps_prev)},
            "fleet_utilization": {"percentage": utilization, "growth": 0.0}
        }
    return cached_call("analytics_overview", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

@router.get("/trends")
def get_analytics_trends(
    period: str = "daily", 
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        now = datetime.now(UTC)
        seven_days_ago = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        dates = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]
        dates_str = [d.isoformat() for d in dates]

        # Revenue per day in one query
        rev_rows = db.exec(
            select(
                cast(Transaction.created_at, Date).label("day"),
                func.sum(Transaction.amount).label("total")
            ).where(
                Transaction.status == TransactionStatus.SUCCESS,
                Transaction.created_at >= seven_days_ago
            ).group_by(cast(Transaction.created_at, Date))
        ).all()
        rev_map = {r.day: float(r.total) for r in rev_rows}

        # Swaps per day in one query
        swap_rows = db.exec(
            select(
                cast(SwapSession.created_at, Date).label("day"),
                func.count(SwapSession.id).label("total")
            ).where(
                SwapSession.created_at >= seven_days_ago
            ).group_by(cast(SwapSession.created_at, Date))
        ).all()
        swap_map = {r.day: r.total for r in swap_rows}

        revenue_data = [rev_map.get(d, 0.0) for d in dates]
        swaps_data = [swap_map.get(d, 0) for d in dates]

        return {
            "dates": dates_str,
            "revenue": revenue_data,
            "swaps": swaps_data
        }
    return cached_call("analytics_trends", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

@router.get("/battery-health-distribution")
def get_battery_health_distribution(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        row = db.exec(
            select(
                func.coalesce(func.sum(case((Battery.health_status == BatteryHealth.EXCELLENT, 1), else_=0)), 0).label("excellent"),
                func.coalesce(func.sum(case((Battery.health_status == BatteryHealth.GOOD, 1), else_=0)), 0).label("good"),
                func.coalesce(func.sum(case((Battery.health_status == BatteryHealth.FAIR, 1), else_=0)), 0).label("fair"),
                func.coalesce(func.sum(case((Battery.health_status == BatteryHealth.CRITICAL, 1), else_=0)), 0).label("critical"),
                func.coalesce(func.sum(case((Battery.health_status == BatteryHealth.POOR, 1), else_=0)), 0).label("poor"),
            )
        ).one()
        return [
            {"status": "Excellent", "count": row.excellent, "color": "#10B981"},
            {"status": "Good", "count": row.good + row.poor, "color": "#3B82F6"},
            {"status": "Fair", "count": row.fair, "color": "#F59E0B"},
            {"status": "Critical", "count": row.critical, "color": "#EF4444"}
        ]
    return cached_call("analytics_battery_health", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

@router.get("/revenue/by-region")
def get_revenue_by_region(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        statement = select(
            Station.city, 
            func.count(SwapSession.id).label("swaps_count")
        ).join(SwapSession, Station.id == SwapSession.station_id).group_by(Station.city)
        
        results = db.exec(statement).all()
        
        if not results:
            return [
                {"region": "Bengaluru", "value": 0},
                {"region": "Mumbai", "value": 0},
            ]
            
        return [{"region": r.city or "Unknown", "value": r.swaps_count * 50} for r in results]
    return cached_call("analytics_rev_region", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

@router.get("/revenue/by-station")
def get_revenue_by_station(
    period: str = "30d", 
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        statement = select(
            Station.name, 
            func.count(SwapSession.id).label("swaps_count")
        ).join(SwapSession, Station.id == SwapSession.station_id).group_by(Station.name).order_by(func.count(SwapSession.id).desc()).limit(5)
        
        results = db.exec(statement).all()
        if not results:
            return [{"station": "No Data", "value": 0}]
            
        return [{"station": r.name, "value": r.swaps_count * 50} for r in results]
    return cached_call("analytics_rev_station", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

@router.get("/recent-activity")
def get_recent_activity(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        swaps = db.exec(
            select(SwapSession, Station.name)
            .join(Station, SwapSession.station_id == Station.id)
            .order_by(SwapSession.created_at.desc())
            .limit(5)
        ).all()
        
        activities = []
        for swap, station_name in swaps:
            activities.append({
                "id": swap.id,
                "type": "swap",
                "description": f"Battery swap at {station_name}",
                "timestamp": swap.created_at.isoformat()
            })
        
        return activities
    return cached_call("analytics_recent_activity", ttl_seconds=60, call=_fetch)

@router.get("/top-stations")
def get_top_stations(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        statement = select(
            Station,
            func.count(SwapSession.id).label("swap_count")
        ).outerjoin(SwapSession, Station.id == SwapSession.station_id).group_by(Station.id).order_by(func.count(SwapSession.id).desc()).limit(3)
        
        results = db.exec(statement).all()
        if not results:
            return [{"id": 0, "name": "No Data", "swaps": 0, "revenue": 0, "status": "active"}]

        return [
            {
                "id": st.id, 
                "name": st.name, 
                "swaps": count, 
                "revenue": count * 50, 
                "status": st.status
            } for st, count in results
        ]
    return cached_call("analytics_top_stations", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

@router.get("/conversion-funnel")
def get_conversion_funnel(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        # User counts in one query
        user_row = db.exec(
            select(
                func.count(User.id).label("signups"),
                func.coalesce(func.sum(case((User.kyc_status == KYCStatus.APPROVED, 1), else_=0)), 0).label("kyc_approved"),
            )
        ).one()
        signups = user_row.signups or 0
        kyc_approved = user_row.kyc_approved or 0

        active_swappers = db.exec(select(func.count(func.distinct(SwapSession.user_id)))).one() or 0
        
        return [
            {"stage": "Visitors", "value": signups * 3 if signups > 0 else 100},
            {"stage": "Signups", "value": signups},
            {"stage": "KYC Approved", "value": kyc_approved},
            {"stage": "First Swap", "value": active_swappers}
        ]
    return cached_call("analytics_funnel", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

@router.get("/demand-forecast")
def get_demand_forecast(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        now = datetime.now(UTC)
        dates = [(now + timedelta(days=i)).date() for i in range(1, 5)]
        
        base_demand = db.exec(select(func.count(SwapSession.id))).one() or 100
        avg_daily = max(50, base_demand // 30)
        
        return {
            "dates": [d.isoformat() for d in dates],
            "forecast": [avg_daily + (i * 5) for i in range(4)],
            "lower_bound": [avg_daily - 10 + (i * 5) for i in range(4)],
            "upper_bound": [avg_daily + 20 + (i * 5) for i in range(4)]
        }
    return cached_call("analytics_demand_forecast", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

@router.get("/inventory-status")
def get_inventory_status(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    def _fetch():
        row = db.exec(
            select(
                func.coalesce(func.sum(case((Battery.status == BatteryStatus.AVAILABLE, 1), else_=0)), 0).label("available"),
                func.coalesce(func.sum(case((Battery.status == BatteryStatus.RENTED, 1), else_=0)), 0).label("rented"),
                func.coalesce(func.sum(case((Battery.status == BatteryStatus.MAINTENANCE, 1), else_=0)), 0).label("maintenance"),
            )
        ).one()
        return {
            "available": row.available,
            "in_transit": row.rented // 10,
            "maintenance": row.maintenance,
            "dispatched": row.rented
        }
    return cached_call("analytics_inventory", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)
