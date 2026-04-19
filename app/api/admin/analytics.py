from __future__ import annotations
from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from sqlmodel import Session, select, func
from sqlalchemy import cast, Date, Integer
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
from app.api import deps

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
    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)
    
    # Revenue (Successful Transactions)
    rev_current = db.exec(select(func.sum(Transaction.amount)).where(
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.created_at >= thirty_days_ago
    )).one() or 0.0
    
    rev_prev = db.exec(select(func.sum(Transaction.amount)).where(
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.created_at >= sixty_days_ago,
        Transaction.created_at < thirty_days_ago
    )).one() or 0.0
    
    # Active Users
    users_total = db.exec(select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)).one() or 0
    users_prev = db.exec(select(func.count(User.id)).where(
        User.status == UserStatus.ACTIVE,
        User.created_at < thirty_days_ago
    )).one() or 0
    
    # Swap Sessions
    swaps_current = db.exec(select(func.count(SwapSession.id)).where(SwapSession.created_at >= thirty_days_ago)).one() or 0
    swaps_prev = db.exec(select(func.count(SwapSession.id)).where(
        SwapSession.created_at >= sixty_days_ago, 
        SwapSession.created_at < thirty_days_ago
    )).one() or 0

    # Utilization (Rented / Total)
    total_batteries = db.exec(select(func.count(Battery.id))).one() or 1
    rented_batteries = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.RENTED)).one() or 0
    utilization = round((rented_batteries / total_batteries) * 100, 1)

    return {
        "revenue": {"total": float(rev_current), "growth": get_percentage_change(float(rev_current), float(rev_prev))},
        "active_users": {"total": users_total, "growth": get_percentage_change(users_total, users_prev)},
        "battery_swaps": {"total": swaps_current, "growth": get_percentage_change(swaps_current, swaps_prev)},
        "fleet_utilization": {"percentage": utilization, "growth": 0.0}
    }

@router.get("/trends")
def get_analytics_trends(
    period: str = "daily", 
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    # Returns last 7 days of revenue and swaps
    now = datetime.now(UTC)
    dates = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]
    dates_str = [d.isoformat() for d in dates]
    
    revenue_data = []
    swaps_data = []
    
    for d in dates:
        start_of_day = datetime.combine(d, datetime.min.time()).replace(tzinfo=UTC)
        end_of_day = start_of_day + timedelta(days=1)
        
        rev = db.exec(select(func.sum(Transaction.amount)).where(
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.created_at >= start_of_day,
            Transaction.created_at < end_of_day
        )).one() or 0.0
        revenue_data.append(float(rev))
        
        swaps = db.exec(select(func.count(SwapSession.id)).where(
            SwapSession.created_at >= start_of_day,
            SwapSession.created_at < end_of_day
        )).one() or 0
        swaps_data.append(swaps)

    return {
        "dates": dates_str,
        "revenue": revenue_data,
        "swaps": swaps_data
    }

@router.get("/battery-health")
def get_battery_health_distribution(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    excellent = db.exec(select(func.count(Battery.id)).where(Battery.health_status == BatteryHealth.EXCELLENT)).one() or 0
    good = db.exec(select(func.count(Battery.id)).where(Battery.health_status == BatteryHealth.GOOD)).one() or 0
    fair = db.exec(select(func.count(Battery.id)).where(Battery.health_status == BatteryHealth.FAIR)).one() or 0
    critical = db.exec(select(func.count(Battery.id)).where(Battery.health_status == BatteryHealth.CRITICAL)).one() or 0
    poor = db.exec(select(func.count(Battery.id)).where(Battery.health_status == BatteryHealth.POOR)).one() or 0

    return [
        {"status": "Excellent", "count": excellent, "color": "#10B981"},
        {"status": "Good", "count": good + poor, "color": "#3B82F6"},
        {"status": "Fair", "count": fair, "color": "#F59E0B"},
        {"status": "Critical", "count": critical, "color": "#EF4444"}
    ]

@router.get("/revenue-by-region")
def get_revenue_by_region(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    # Group by station.city
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

@router.get("/revenue/station")
def get_revenue_by_station(
    period: str = "30d", 
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    statement = select(
        Station.name, 
        func.count(SwapSession.id).label("swaps_count")
    ).join(SwapSession, Station.id == SwapSession.station_id).group_by(Station.name).order_by(func.count(SwapSession.id).desc()).limit(5)
    
    results = db.exec(statement).all()
    if not results:
        return [{"station": "No Data", "value": 0}]
        
    return [{"station": r.name, "value": r.swaps_count * 50} for r in results]

@router.get("/recent-activity")
def get_recent_activity(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
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

@router.get("/top-stations")
def get_top_stations(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
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

@router.get("/conversion-funnel")
def get_conversion_funnel(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    signups = db.exec(select(func.count(User.id))).one() or 0
    kyc_approved = db.exec(select(func.count(User.id)).where(User.kyc_status == KYCStatus.APPROVED)).one() or 0
    
    active_swappers = db.exec(select(func.count(func.distinct(SwapSession.user_id)))).one() or 0
    
    return [
        {"stage": "Visitors", "value": signups * 3 if signups > 0 else 100},
        {"stage": "Signups", "value": signups},
        {"stage": "KYC Approved", "value": kyc_approved},
        {"stage": "First Swap", "value": active_swappers}
    ]

@router.get("/demand-forecast")
def get_demand_forecast(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
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

@router.get("/inventory-status")
def get_inventory_status(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db)
):
    available = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.AVAILABLE)).one() or 0
    rented = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.RENTED)).one() or 0
    maintenance = db.exec(select(func.count(Battery.id)).where(Battery.status == BatteryStatus.MAINTENANCE)).one() or 0
    
    return {
        "available": available,
        "in_transit": rented // 10,
        "maintenance": maintenance,
        "dispatched": rented
    }
