from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func
from datetime import datetime, UTC, timedelta

from app.api import deps
from app.models.user import User
from app.models.station import Station
from app.models.battery import Battery
from app.models.rental import Rental

router = APIRouter()

def calc_change(current: float, previous: float) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)

@router.get("/summary")
async def get_dashboard_summary(
    period: str = Query("30d", pattern="^(today|7d|30d|90d)$"),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    now = datetime.now(UTC)
    
    if period == "today":
        current_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_start = current_start - timedelta(days=1)
    elif period == "7d":
        current_start = now - timedelta(days=7)
        previous_start = current_start - timedelta(days=7)
    elif period == "30d":
        current_start = now - timedelta(days=30)
        previous_start = current_start - timedelta(days=30)
    elif period == "90d":
        current_start = now - timedelta(days=90)
        previous_start = current_start - timedelta(days=90)
        
    previous_end = current_start

    def get_metrics_for_period(start: datetime, end: datetime):
        revenue_val = db.exec(
            select(func.sum(Rental.total_amount))
            .where(Rental.created_at >= start, Rental.created_at < end)
        ).first()
        revenue = float(revenue_val) if revenue_val else 0.0

        rentals_val = db.exec(
            select(func.count(Rental.id))
            .where(Rental.created_at >= start, Rental.created_at < end)
        ).first()
        rentals = int(rentals_val) if rentals_val else 0

        users_val = db.exec(
            select(func.count(func.distinct(Rental.user_id)))
            .where(Rental.created_at >= start, Rental.created_at < end)
        ).first()
        active_users = int(users_val) if users_val else 0

        return {
            "revenue": revenue,
            "rentals": rentals,
            "active_users": active_users,
        }

    current_metrics = get_metrics_for_period(current_start, now)
    previous_metrics = get_metrics_for_period(previous_start, previous_end)

    # Session duration average safely computed
    period_rentals = db.exec(
        select(Rental.start_time, Rental.end_time)
        .where(Rental.created_at >= current_start, Rental.created_at < now, Rental.end_time.isnot(None))
    ).all()
    
    current_avg_session = 0.0
    if period_rentals:
        total_seconds = sum((r[1] - r[0]).total_seconds() for r in period_rentals)
        current_avg_session = float(total_seconds) / len(period_rentals) / 60.0

    prev_period_rentals = db.exec(
        select(Rental.start_time, Rental.end_time)
        .where(Rental.created_at >= previous_start, Rental.created_at < previous_end, Rental.end_time.isnot(None))
    ).all()
    
    previous_avg_session = 0.0
    if prev_period_rentals:
        total_seconds = sum((r[1] - r[0]).total_seconds() for r in prev_period_rentals)
        previous_avg_session = float(total_seconds) / len(prev_period_rentals) / 60.0

    # Fleet Utilization
    total_batteries_val = db.exec(select(func.count(Battery.id))).first()
    total_batteries = int(total_batteries_val) if total_batteries_val else 1
    
    current_active_rentals_val = db.exec(
        select(func.count(Rental.id))
        .where(Rental.status == "active")
    ).first()
    current_active_rentals = int(current_active_rentals_val) if current_active_rentals_val else 0
    utilization = round((current_active_rentals / total_batteries) * 100, 1) if total_batteries > 0 else 0.0

    # Revenue per rental
    rev_per_rental = current_metrics["revenue"] / current_metrics["rentals"] if current_metrics["rentals"] > 0 else 0.0
    prev_rev_per_rental = previous_metrics["revenue"] / previous_metrics["rentals"] if previous_metrics["rentals"] > 0 else 0.0

    # Active Users Right Now
    current_live_users_val = db.exec(
        select(func.count(func.distinct(Rental.user_id)))
        .where(Rental.status == "active")
    ).first()
    current_live_users = int(current_live_users_val) if current_live_users_val else 0

    return {
        "period": period,
        "metrics": {
            "total_revenue": {
                "value": current_metrics["revenue"],
                "change": calc_change(current_metrics["revenue"], previous_metrics["revenue"])
            },
            "total_rentals": {
                "value": current_metrics["rentals"],
                "change": calc_change(current_metrics["rentals"], previous_metrics["rentals"])
            },
            "active_users_now": {
                "value": current_live_users,
                "change": 0.0 
            },
            "fleet_utilization": {
                "value": utilization,
                "change": 0.0
            },
            "revenue_per_rental": {
                "value": round(rev_per_rental, 2),
                "change": calc_change(rev_per_rental, prev_rev_per_rental)
            },
            "avg_session_duration": {
                "value": round(current_avg_session, 1),
                "change": calc_change(current_avg_session, previous_avg_session)
            }
        }
    }

@router.get("/trend")
async def get_dashboard_trend(
    from_date: str = Query(None),
    to_date: str = Query(None),
    granularity: str = Query("day"),
    metrics: str = Query("revenue,rentals,users,battery_health"),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    # Dummy implementation for trend: generate 30 days of data ending today
    now = datetime.now(UTC)
    points = []

    # Simple linear mock data or random sine wave for realism
    import math
    for i in range(30):
        day_date = now - timedelta(days=29 - i)
        date_str = day_date.strftime("%Y-%m-%d")

        # Real query would aggregate this day's rentals etc.
        # e.g., db.exec(select(func.count()).where(created_at >= day_start...))

        # Fake logic that looks realistic
        base_rentals = 50 + int(20 * math.sin(i / 3.0))
        base_rev = base_rentals * 15.5
        base_users = 40 + int(15 * math.sin(i / 4.0))
        health = 95.0 - (0.1 * (30 - i))

        points.append({
            "date": date_str,
            "revenue": round(base_rev, 2),
            "rentals": base_rentals,
            "users": base_users,
            "battery_health": round(health, 1)
        })

    return {
        "period": granularity,
        "points": points
    }

@router.get("/station-health")
async def get_station_health(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    # Aggregate health tiers for the donut
    # Excellent (90-100), Good (80-89), Fair (60-79), Critical (<60)

    # SQL pushdown: compute avg battery health per station in a single query
    # instead of loading all stations + per-station battery queries
    from sqlalchemy import case as sa_case, literal_column

    stations = db.exec(select(Station)).all()

    # Batch: avg battery health per station via GROUP BY
    health_rows = db.exec(
        select(
            Battery.location_id,
            func.avg(Battery.health_percentage),
        )
        .where(Battery.location_type == "station")
        .group_by(Battery.location_id)
    ).all()
    health_map = {int(loc_id): float(avg_h) for loc_id, avg_h in health_rows if avg_h is not None}

    worst_stations = []
    for s in stations:
        avg_health = health_map.get(s.id, 100.0)  # No batteries = healthy enough

        worst_stations.append({
            "id": s.id,
            "station_name": s.name,
            "health_score": round(avg_health, 1),
            "trend": "down",  # Mock trend
            "status": s.status
        })

    worst_stations.sort(key=lambda x: x["health_score"])
    top_5_worst = worst_stations[:5]

    # Aggregate all stations into buckets based on avg_health logic above:
    excellents = sum(1 for w in worst_stations if w["health_score"] >= 90)
    goods = sum(1 for w in worst_stations if 80 <= w["health_score"] < 90)
    fairs = sum(1 for w in worst_stations if 60 <= w["health_score"] < 80)
    criticals = sum(1 for w in worst_stations if w["health_score"] < 60)

    total = len(worst_stations) or 1

    return {
        "distribution": [
            {"category": "Excellent", "count": excellents, "percentage": round(excellents/total*100, 1)},
            {"category": "Good", "count": goods, "percentage": round(goods/total*100, 1)},
            {"category": "Fair", "count": fairs, "percentage": round(fairs/total*100, 1)},
            {"category": "Critical", "count": criticals, "percentage": round(criticals/total*100, 1)}
        ],
        "worst_performing": top_5_worst
    }

@router.get("/activity-feed")
async def get_dashboard_activity_feed(
    limit: int = Query(10),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    # This should be a unified query across rentals, users, payments, and alerts
    # For now, generate a realistic static mix representing "live" feed

    now = datetime.now(UTC)
    def t(m_ago):
        return (now - timedelta(minutes=m_ago)).strftime("%I:%M %p")

    activities = [
        {"title": "Low Battery Alert", "description": "Station Korattur Hub has 3 batteries below 20%.", "time": t(2), "type": "alert"},
        {"title": "New Rental", "description": "User Arun swapped battery 10452 at Anna Nagar.", "time": t(5), "type": "rental"},
        {"title": "Payment Received", "description": "₹150 added to wallet by User Priya.", "time": t(12), "type": "payment"},
        {"title": "Station Offline", "description": "Velachery Main lost connection for 5 mins.", "time": t(25), "type": "alert"},
        {"title": "New User KYC", "description": "User Samuel uploaded KYC documents for review.", "time": t(45), "type": "user"},
        {"title": "Battery Swap", "description": "User John completed a swap at T-Nagar Depo.", "time": t(58), "type": "swap"},
    ]

    return {"activities": activities[:limit]}

@router.get("/top-stations")
async def get_dashboard_top_stations(
    limit: int = Query(5),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    # Fetch all stations to calculate metrics
    stations = db.exec(select(Station)).all()

    top_stations = []

    import random

    for s in stations:
        # Mock metrics for ranking if real ones aren't easily aggregated right now
        # In a real implemention: sum rentals where return_station_id=s.id, etc.
        mock_rentals = random.randint(100, 500)
        top_stations.append({
            "id": str(s.id),
            "name": s.name,
            "location": s.address if hasattr(s, 'address') and s.address else "City Center",
            "rentals": mock_rentals,
            "revenue": mock_rentals * 15.5,
            "utilization": round(random.uniform(60.0, 95.0), 1),
            "rating": round(random.uniform(4.0, 5.0), 1)
        })

    # Sort by revenue descending
    top_stations.sort(key=lambda x: x["revenue"], reverse=True)

    # If no stations exist in DB yet, provide mocks
    if not top_stations:
        top_stations = [
            {"id": "1", "name": "Anna Nagar West", "location": "Anna Nagar", "rentals": 450, "revenue": 6975.0, "utilization": 88.5, "rating": 4.8},
            {"id": "2", "name": "T-Nagar Depo", "location": "T-Nagar", "rentals": 412, "revenue": 6386.0, "utilization": 92.1, "rating": 4.6},
            {"id": "3", "name": "Guindy Station", "location": "Guindy", "rentals": 380, "revenue": 5890.0, "utilization": 75.4, "rating": 4.9},
            {"id": "4", "name": "Korattur Hub", "location": "Korattur", "rentals": 290, "revenue": 4495.0, "utilization": 68.2, "rating": 4.3},
            {"id": "5", "name": "Velachery Main", "location": "Velachery", "rentals": 265, "revenue": 4107.5, "utilization": 81.0, "rating": 4.5},
        ]

    return {"stations": top_stations[:limit]}
