from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func, case
from datetime import datetime, UTC, timedelta

from app.api import deps
from app.models.user import User
from app.models.station import Station
from app.models.battery import Battery
from app.models.rental import Rental
from app.utils.runtime_cache import cached_call
from app.core.config import settings

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
    def _load():
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

        # --- Single query for both periods: revenue, rental count, active users ---
        row = db.exec(
            select(
                # Current period
                func.coalesce(func.sum(case(
                    (Rental.created_at >= current_start, Rental.total_amount), else_=0
                )), 0),
                func.coalesce(func.sum(case(
                    (Rental.created_at >= current_start, 1), else_=0
                )), 0),
                # Previous period
                func.coalesce(func.sum(case(
                    (Rental.created_at >= previous_start, case(
                        (Rental.created_at < previous_end, Rental.total_amount), else_=0
                    )), else_=0
                )), 0),
                func.coalesce(func.sum(case(
                    (Rental.created_at >= previous_start, case(
                        (Rental.created_at < previous_end, 1), else_=0
                    )), else_=0
                )), 0),
            ).where(Rental.created_at >= previous_start)
        ).one()
        curr_rev, curr_rentals = float(row[0]), int(row[1])
        prev_rev, prev_rentals = float(row[2]), int(row[3])

        # Avg session duration via SQL (current + previous)
        avg_session_row = db.exec(
            select(
                func.avg(case(
                    (Rental.created_at >= current_start,
                     func.extract("epoch", Rental.end_time) - func.extract("epoch", Rental.start_time)),
                    else_=None
                )),
                func.avg(case(
                    (Rental.created_at >= previous_start, case(
                        (Rental.created_at < previous_end,
                         func.extract("epoch", Rental.end_time) - func.extract("epoch", Rental.start_time)),
                        else_=None
                    )),
                    else_=None
                )),
            ).where(
                Rental.created_at >= previous_start,
                Rental.end_time.isnot(None),
            )
        ).one()
        current_avg_session = float(avg_session_row[0]) / 60.0 if avg_session_row[0] else 0.0
        previous_avg_session = float(avg_session_row[1]) / 60.0 if avg_session_row[1] else 0.0

        # Fleet utilization + live users (2 queries)
        fleet_row = db.exec(
            select(
                func.count(Battery.id),
            )
        ).one()
        total_batteries = int(fleet_row) if fleet_row else 1

        live_row = db.exec(
            select(
                func.count(Rental.id),
                func.count(func.distinct(Rental.user_id)),
            ).where(Rental.status == "active")
        ).one()
        current_active_rentals = int(live_row[0]) if live_row[0] else 0
        current_live_users = int(live_row[1]) if live_row[1] else 0

        utilization = round((current_active_rentals / total_batteries) * 100, 1) if total_batteries > 0 else 0.0

        # Revenue per rental
        rev_per_rental = curr_rev / curr_rentals if curr_rentals > 0 else 0.0
        prev_rev_per_rental = prev_rev / prev_rentals if prev_rentals > 0 else 0.0

        return {
            "period": period,
            "metrics": {
                "total_revenue": {
                    "value": curr_rev,
                    "change": calc_change(curr_rev, prev_rev)
                },
                "total_rentals": {
                    "value": curr_rentals,
                    "change": calc_change(curr_rentals, prev_rentals)
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

    return cached_call("admin-dashboard", "summary", period, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)

@router.get("/trend")
async def get_dashboard_trend(
    from_date: str = Query(None),
    to_date: str = Query(None),
    granularity: str = Query("day"),
    metrics: str = Query("revenue,rentals,users,battery_health"),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    def _load():
        now = datetime.now(UTC)
        start = now - timedelta(days=30)

        # Real data: daily aggregation from Rental table
        rows = db.exec(
            select(
                func.date(Rental.created_at),
                func.coalesce(func.sum(Rental.total_amount), 0),
                func.count(Rental.id),
                func.count(func.distinct(Rental.user_id)),
            )
            .where(Rental.created_at >= start)
            .group_by(func.date(Rental.created_at))
            .order_by(func.date(Rental.created_at))
        ).all()
        day_map = {str(r[0]): {"revenue": round(float(r[1]), 2), "rentals": int(r[2]), "users": int(r[3])} for r in rows if r[0]}

        # Battery health avg (single value, slow-changing)
        avg_health = db.exec(select(func.coalesce(func.avg(Battery.health_percentage), 95.0))).one()
        avg_health_val = round(float(avg_health), 1)

        points = []
        for i in range(30):
            day_date = now - timedelta(days=29 - i)
            date_str = str(day_date.date())
            day_data = day_map.get(date_str, {"revenue": 0, "rentals": 0, "users": 0})
            points.append({
                "date": day_date.strftime("%Y-%m-%d"),
                "revenue": day_data["revenue"],
                "rentals": day_data["rentals"],
                "users": day_data["users"],
                "battery_health": avg_health_val,
            })

        return {"period": granularity, "points": points}

    return cached_call("admin-dashboard", "trend", granularity, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)

@router.get("/station-health")
async def get_station_health(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    def _load():
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
            avg_health = health_map.get(s.id, 100.0)
            worst_stations.append({
                "id": s.id,
                "station_name": s.name,
                "health_score": round(avg_health, 1),
                "trend": "down",
                "status": s.status
            })

        worst_stations.sort(key=lambda x: x["health_score"])
        top_5_worst = worst_stations[:5]

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

    return cached_call("admin-dashboard", "station-health", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)

@router.get("/activity-feed")
async def get_dashboard_activity_feed(
    limit: int = Query(10),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    def _load():
        # Pull recent real rentals as activity items
        recent_rentals = db.exec(
            select(Rental.id, Rental.user_id, Rental.station_id, Rental.created_at)
            .order_by(Rental.created_at.desc())
            .limit(limit)
        ).all()

        user_ids = {r[1] for r in recent_rentals if r[1]}
        station_ids = {r[2] for r in recent_rentals if r[2]}
        user_map = {u.id: u.full_name for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
        station_map = {s.id: s.name for s in db.exec(select(Station).where(Station.id.in_(station_ids))).all()} if station_ids else {}

        activities = []
        for r in recent_rentals:
            user_name = user_map.get(r[1], "Unknown")
            station_name = station_map.get(r[2], "Unknown Station")
            time_str = r[3].strftime("%I:%M %p") if r[3] else ""
            activities.append({
                "title": "New Rental",
                "description": f"User {user_name} started a rental at {station_name}.",
                "time": time_str,
                "type": "rental",
            })

        if not activities:
            now = datetime.now(UTC)
            activities = [{"title": "No recent activity", "description": "System is idle.", "time": now.strftime("%I:%M %p"), "type": "info"}]

        return {"activities": activities}

    return cached_call("admin-dashboard", "activity-feed", limit, ttl_seconds=60, call=_load)

@router.get("/top-stations")
async def get_dashboard_top_stations(
    limit: int = Query(5),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    def _load():
        # Real data: top stations by rental count in last 30 days
        since = datetime.now(UTC) - timedelta(days=30)

        # Find which station column links to Rental
        # Rentals usually have a pickup/return station_id. Use a subquery.
        station_rows = db.exec(
            select(
                Station.id,
                Station.name,
                Station.address,
                Station.rating,
                func.count(Rental.id).label("rental_count"),
                func.coalesce(func.sum(Rental.total_amount), 0).label("total_rev"),
            )
            .outerjoin(Rental, Rental.station_id == Station.id)
            .where(Rental.created_at >= since)
            .group_by(Station.id, Station.name, Station.address, Station.rating)
            .order_by(func.count(Rental.id).desc())
            .limit(limit)
        ).all()

        # Battery utilization per station
        util_rows = db.exec(
            select(
                Battery.station_id,
                func.count(Battery.id),
                func.coalesce(func.sum(case((Battery.status == "rented", 1), else_=0)), 0),
            )
            .where(Battery.station_id.isnot(None))
            .group_by(Battery.station_id)
        ).all()
        util_map = {
            int(r[0]): round(int(r[2]) / max(int(r[1]), 1) * 100, 1)
            for r in util_rows if r[0]
        }

        top_stations = []
        for r in station_rows:
            top_stations.append({
                "id": str(r[0]),
                "name": r[1],
                "location": r[2] or "N/A",
                "rentals": int(r[4]),
                "revenue": round(float(r[5]), 2),
                "utilization": util_map.get(r[0], 0.0),
                "rating": round(float(r[3]), 1) if r[3] else 4.0,
            })

        # Fallback if no data
        if not top_stations:
            top_stations = [{"id": "0", "name": "No data", "location": "-", "rentals": 0, "revenue": 0, "utilization": 0, "rating": 0}]

        return {"stations": top_stations}

    return cached_call("admin-dashboard", "top-stations", limit, ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)
