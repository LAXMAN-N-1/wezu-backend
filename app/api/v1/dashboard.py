from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone; UTC = timezone.utc
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from app.api import deps
from app.models.battery import Battery, BatteryHealthHistory
from app.models.financial import Transaction
from app.models.rental import Rental
from app.models.station import Station
from app.models.user import User

router = APIRouter()

_ALLOWED_METRICS = {"revenue", "rentals", "users", "battery_health"}
_ALLOWED_GRANULARITY = {"day", "week", "month"}


def calc_change(current: float, previous: float) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _parse_iso_datetime(value: str | None, *, field_name: str, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    try:
        if "T" not in raw and len(raw) == 10:
            parsed_date = date.fromisoformat(raw)
            parsed_time = time.max if end_of_day else time.min
            parsed = datetime.combine(parsed_date, parsed_time, tzinfo=UTC)
        else:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            else:
                parsed = parsed.astimezone(UTC)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name}. Use ISO-8601 date or datetime.",
        ) from exc

    return parsed


def _bucket_start(ts: datetime, granularity: str) -> datetime:
    aligned = ts.astimezone(UTC)
    if granularity == "day":
        return aligned.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "week":
        day_start = aligned.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start - timedelta(days=day_start.weekday())
    if granularity == "month":
        return aligned.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise HTTPException(status_code=400, detail="Unsupported granularity")


def _advance_bucket(ts: datetime, granularity: str) -> datetime:
    if granularity == "day":
        return ts + timedelta(days=1)
    if granularity == "week":
        return ts + timedelta(days=7)
    if granularity == "month":
        year = ts.year + (1 if ts.month == 12 else 0)
        month = 1 if ts.month == 12 else ts.month + 1
        return ts.replace(year=year, month=month, day=1)
    raise HTTPException(status_code=400, detail="Unsupported granularity")


def _time_ago(now: datetime, ts: datetime) -> str:
    seconds = int(max(0, (now - ts).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} hr ago"
    return f"{seconds // 86400} day ago" if seconds < 172800 else f"{seconds // 86400} days ago"


def _resolve_station_id(battery: Battery) -> int | None:
    if battery.station_id is not None:
        return battery.station_id
    location_type = _status_text(battery.location_type).lower()
    if location_type == "station" and battery.location_id is not None:
        return battery.location_id
    return None


def _status_text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


@router.get("/summary")
async def get_dashboard_summary(
    period: str = Query("30d", pattern="^(today|7d|30d|90d)$"),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    _ = current_user
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
    else:  # 90d
        current_start = now - timedelta(days=90)
        previous_start = current_start - timedelta(days=90)

    previous_end = current_start

    def get_metrics_for_period(start: datetime, end: datetime) -> dict[str, float | int]:
        revenue_val = db.exec(
            select(func.sum(Rental.total_amount)).where(Rental.start_time >= start, Rental.start_time < end)
        ).first()
        revenue = float(revenue_val) if revenue_val else 0.0

        rentals_val = db.exec(
            select(func.count(Rental.id)).where(Rental.start_time >= start, Rental.start_time < end)
        ).first()
        rentals = int(rentals_val) if rentals_val else 0

        users_val = db.exec(
            select(func.count(func.distinct(Rental.user_id))).where(Rental.start_time >= start, Rental.start_time < end)
        ).first()
        active_users = int(users_val) if users_val else 0

        return {
            "revenue": revenue,
            "rentals": rentals,
            "active_users": active_users,
        }

    current_metrics = get_metrics_for_period(current_start, now)
    previous_metrics = get_metrics_for_period(previous_start, previous_end)

    # Compute avg session duration in SQL rather than loading every rental row
    # into Python. Returns duration in minutes (epoch seconds / 60).
    def _avg_session_minutes(range_start: datetime, range_end: datetime) -> float:
        duration_seconds = func.extract(
            "epoch", Rental.end_time - Rental.start_time
        )
        avg_seconds = db.exec(
            select(func.avg(duration_seconds)).where(
                Rental.start_time >= range_start,
                Rental.start_time < range_end,
                Rental.end_time.isnot(None),
                Rental.end_time > Rental.start_time,
            )
        ).first()
        return float(avg_seconds) / 60.0 if avg_seconds else 0.0

    current_avg_session = _avg_session_minutes(current_start, now)
    previous_avg_session = _avg_session_minutes(previous_start, previous_end)

    total_batteries_val = db.exec(select(func.count(Battery.id))).first()
    total_batteries = int(total_batteries_val) if total_batteries_val else 0

    current_active_rentals_val = db.exec(select(func.count(Rental.id)).where(Rental.status == "active")).first()
    current_active_rentals = int(current_active_rentals_val) if current_active_rentals_val else 0
    utilization = round((current_active_rentals / total_batteries) * 100, 1) if total_batteries > 0 else 0.0

    rev_per_rental = (
        float(current_metrics["revenue"]) / int(current_metrics["rentals"]) if int(current_metrics["rentals"]) > 0 else 0.0
    )
    prev_rev_per_rental = (
        float(previous_metrics["revenue"]) / int(previous_metrics["rentals"]) if int(previous_metrics["rentals"]) > 0 else 0.0
    )

    current_live_users_val = db.exec(select(func.count(func.distinct(Rental.user_id))).where(Rental.status == "active")).first()
    current_live_users = int(current_live_users_val) if current_live_users_val else 0

    return {
        "period": period,
        "metrics": {
            "total_revenue": {
                "value": float(current_metrics["revenue"]),
                "change": calc_change(float(current_metrics["revenue"]), float(previous_metrics["revenue"])),
            },
            "total_rentals": {
                "value": int(current_metrics["rentals"]),
                "change": calc_change(float(current_metrics["rentals"]), float(previous_metrics["rentals"])),
            },
            "active_users_now": {
                "value": current_live_users,
                "change": calc_change(float(current_metrics["active_users"]), float(previous_metrics["active_users"])),
            },
            "fleet_utilization": {
                "value": utilization,
                "change": 0.0,
            },
            "revenue_per_rental": {
                "value": round(rev_per_rental, 2),
                "change": calc_change(rev_per_rental, prev_rev_per_rental),
            },
            "avg_session_duration": {
                "value": round(current_avg_session, 1),
                "change": calc_change(current_avg_session, previous_avg_session),
            },
        },
    }


@router.get("/trend")
async def get_dashboard_trend(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    granularity: str = Query("day"),
    metrics: str = Query("revenue,rentals,users,battery_health"),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    _ = current_user

    granularity_key = (granularity or "day").strip().lower()
    if granularity_key not in _ALLOWED_GRANULARITY:
        raise HTTPException(status_code=400, detail="granularity must be one of: day, week, month")

    metric_tokens = [token.strip().lower() for token in (metrics or "").split(",") if token.strip()]
    if not metric_tokens:
        metric_tokens = sorted(_ALLOWED_METRICS)
    unknown_metrics = sorted(set(metric_tokens) - _ALLOWED_METRICS)
    if unknown_metrics:
        raise HTTPException(status_code=400, detail=f"Unsupported metrics: {unknown_metrics}")

    now = datetime.now(UTC)
    range_end = _parse_iso_datetime(to_date, field_name="to_date", end_of_day=True) or now
    range_start = _parse_iso_datetime(from_date, field_name="from_date") or (range_end - timedelta(days=29))

    if range_start >= range_end:
        raise HTTPException(status_code=400, detail="from_date must be earlier than to_date")

    start_bucket = _bucket_start(range_start, granularity_key)
    end_bucket = _bucket_start(range_end, granularity_key)

    points: dict[datetime, dict[str, Any]] = {}
    cursor = start_bucket
    while cursor <= end_bucket:
        points[cursor] = {
            "revenue": 0.0,
            "rentals": 0,
            "users": 0,
            "battery_health_sum": 0.0,
            "battery_health_count": 0,
        }
        cursor = _advance_bucket(cursor, granularity_key)

    if not points:
        return {"period": granularity_key, "points": []}

    rental_rows = db.exec(
        select(Rental.start_time, Rental.total_amount)
        .where(Rental.start_time >= range_start)
        .where(Rental.start_time <= range_end)
    ).all()
    for start_time, total_amount in rental_rows:
        if start_time is None:
            continue
        bucket = _bucket_start(start_time if start_time.tzinfo else start_time.replace(tzinfo=UTC), granularity_key)
        if bucket in points:
            points[bucket]["rentals"] += 1
            points[bucket]["revenue"] += float(total_amount or 0.0)

    user_rows = db.exec(
        select(User.created_at).where(User.created_at >= range_start).where(User.created_at <= range_end)
    ).all()
    for row in user_rows:
        created_at = row[0] if isinstance(row, tuple) else row
        if created_at is None:
            continue
        bucket = _bucket_start(created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC), granularity_key)
        if bucket in points:
            points[bucket]["users"] += 1

    health_rows = db.exec(
        select(BatteryHealthHistory.recorded_at, BatteryHealthHistory.health_percentage)
        .where(BatteryHealthHistory.recorded_at >= range_start)
        .where(BatteryHealthHistory.recorded_at <= range_end)
    ).all()
    for recorded_at, health_pct in health_rows:
        if recorded_at is None:
            continue
        bucket = _bucket_start(recorded_at if recorded_at.tzinfo else recorded_at.replace(tzinfo=UTC), granularity_key)
        if bucket in points:
            points[bucket]["battery_health_sum"] += float(health_pct or 0.0)
            points[bucket]["battery_health_count"] += 1

    global_avg_health_val = db.exec(select(func.avg(Battery.health_percentage))).first()
    global_avg_health = round(float(global_avg_health_val), 2) if global_avg_health_val is not None else 0.0

    output_points: list[dict[str, Any]] = []
    for bucket in sorted(points.keys()):
        payload = {"date": bucket.date().isoformat() if granularity_key != "month" else bucket.strftime("%Y-%m")}
        row = points[bucket]

        if "revenue" in metric_tokens:
            payload["revenue"] = round(float(row["revenue"]), 2)
        if "rentals" in metric_tokens:
            payload["rentals"] = int(row["rentals"])
        if "users" in metric_tokens:
            payload["users"] = int(row["users"])
        if "battery_health" in metric_tokens:
            count = int(row["battery_health_count"])
            payload["battery_health"] = (
                round(float(row["battery_health_sum"]) / count, 2) if count > 0 else global_avg_health
            )

        output_points.append(payload)

    return {
        "period": granularity_key,
        "from": range_start.isoformat(),
        "to": range_end.isoformat(),
        "points": output_points,
    }


@router.get("/station-health")
async def get_station_health(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    _ = current_user

    from sqlalchemy import case as sa_case, literal_column

    # Resolved station_id expression for batteries
    _resolved_station = func.coalesce(
        Battery.station_id,
        sa_case(
            (Battery.location_type == "station", Battery.location_id),
            else_=literal_column("NULL"),
        ),
    )

    # 1. Avg health per station — single SQL query instead of loading ALL batteries
    health_rows = db.exec(
        select(
            _resolved_station.label("sid"),
            func.avg(Battery.health_percentage),
        )
        .where(_resolved_station.isnot(None))
        .where(Battery.health_percentage.isnot(None))
        .group_by(literal_column("sid"))
    ).all()
    health_by_station: dict[int, float] = {int(row[0]): round(float(row[1]), 1) for row in health_rows if row[0] is not None}

    # 2. Only load station id/name/status (compact columns)
    stations = db.exec(select(Station.id, Station.name, Station.status)).all()
    if not stations:
        return {
            "distribution": [
                {"category": "Excellent", "count": 0, "percentage": 0.0},
                {"category": "Good", "count": 0, "percentage": 0.0},
                {"category": "Fair", "count": 0, "percentage": 0.0},
                {"category": "Critical", "count": 0, "percentage": 0.0},
            ],
            "worst_performing": [],
        }

    station_ids = [int(s[0]) for s in stations if s[0] is not None]

    # 3. Health history trends — batch via SQL AVG per station per window
    now = datetime.now(UTC)
    current_window_start = now - timedelta(days=7)
    previous_window_start = now - timedelta(days=14)

    # Get battery→station mapping only for batteries at stations (SQL, no full table load)
    battery_station_rows = db.exec(
        select(Battery.id, _resolved_station.label("sid"))
        .where(_resolved_station.in_(station_ids))
    ).all()
    battery_to_station: dict[int, int] = {int(r[0]): int(r[1]) for r in battery_station_rows if r[0] is not None and r[1] is not None}

    history_by_station_current: dict[int, list[float]] = defaultdict(list)
    history_by_station_previous: dict[int, list[float]] = defaultdict(list)

    if battery_to_station:
        history_rows = db.exec(
            select(BatteryHealthHistory.battery_id, BatteryHealthHistory.health_percentage, BatteryHealthHistory.recorded_at)
            .where(BatteryHealthHistory.battery_id.in_(list(battery_to_station.keys())))
            .where(BatteryHealthHistory.recorded_at >= previous_window_start)
            .where(BatteryHealthHistory.recorded_at <= now)
        ).all()

        for battery_id, health_pct, recorded_at in history_rows:
            station_id = battery_to_station.get(int(battery_id))
            if station_id is None:
                continue
            if recorded_at >= current_window_start:
                history_by_station_current[station_id].append(float(health_pct or 0.0))
            else:
                history_by_station_previous[station_id].append(float(health_pct or 0.0))

    worst_stations = []
    for sid, sname, sstatus in stations:
        station_id = int(sid)
        health_score = health_by_station.get(station_id, 0.0)

        current_hist = history_by_station_current.get(station_id, [])
        previous_hist = history_by_station_previous.get(station_id, [])

        if current_hist and previous_hist:
            delta = (sum(current_hist) / len(current_hist)) - (sum(previous_hist) / len(previous_hist))
            if delta >= 1.0:
                trend = "up"
            elif delta <= -1.0:
                trend = "down"
            else:
                trend = "stable"
        elif current_hist:
            trend = "stable"
        else:
            trend = "unknown"

        worst_stations.append(
            {
                "id": sid,
                "station_name": sname,
                "health_score": health_score,
                "trend": trend,
                "status": sstatus,
            }
        )

    worst_stations.sort(key=lambda item: item["health_score"])
    top_5_worst = worst_stations[:5]

    excellents = sum(1 for item in worst_stations if item["health_score"] >= 90)
    goods = sum(1 for item in worst_stations if 80 <= item["health_score"] < 90)
    fairs = sum(1 for item in worst_stations if 60 <= item["health_score"] < 80)
    criticals = sum(1 for item in worst_stations if item["health_score"] < 60)

    total = len(worst_stations)
    denominator = total if total > 0 else 1

    return {
        "distribution": [
            {"category": "Excellent", "count": excellents, "percentage": round(excellents / denominator * 100, 1)},
            {"category": "Good", "count": goods, "percentage": round(goods / denominator * 100, 1)},
            {"category": "Fair", "count": fairs, "percentage": round(fairs / denominator * 100, 1)},
            {"category": "Critical", "count": criticals, "percentage": round(criticals / denominator * 100, 1)},
        ],
        "worst_performing": top_5_worst,
    }


@router.get("/activity-feed")
async def get_dashboard_activity_feed(
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    _ = current_user

    now = datetime.now(UTC)
    source_limit = max(10, min(200, limit * 4))

    station_name_by_id = {
        int(station_id): station_name
        for station_id, station_name in db.exec(select(Station.id, Station.name)).all()
        if station_id is not None
    }

    events: list[dict[str, Any]] = []

    rental_rows = db.exec(
        select(Rental)
        .order_by(Rental.start_time.desc())
        .limit(source_limit)
    ).all()
    for rental in rental_rows:
        ts = rental.start_time or rental.created_at
        station_name = station_name_by_id.get(int(rental.start_station_id), "Unknown station")
        status_text = _status_text(rental.status).replace("_", " ").title() or "Updated"
        events.append(
            {
                "timestamp": ts,
                "title": f"Rental {status_text}",
                "description": f"Rental #{rental.id} at {station_name} for user #{rental.user_id}",
                "type": "rental",
            }
        )

    transaction_rows = db.exec(
        select(Transaction)
        .order_by(Transaction.created_at.desc())
        .limit(source_limit)
    ).all()
    for txn in transaction_rows:
        ts = txn.created_at
        transaction_type = _status_text(txn.transaction_type).replace("_", " ").title() or "Transaction"
        events.append(
            {
                "timestamp": ts,
                "title": f"Payment {transaction_type}",
                "description": f"User #{txn.user_id} paid {txn.currency} {round(float(txn.amount or 0), 2)}",
                "type": "payment",
            }
        )

    user_rows = db.exec(select(User).order_by(User.created_at.desc()).limit(source_limit)).all()
    for user in user_rows:
        ts = user.created_at
        identity = user.full_name or user.email or user.phone_number or f"User #{user.id}"
        events.append(
            {
                "timestamp": ts,
                "title": "New User Registration",
                "description": f"{identity} joined the platform",
                "type": "user",
            }
        )

    low_battery_rows = db.exec(
        select(Battery)
        .where((Battery.current_charge < 20) | (Battery.health_percentage < 60))
        .order_by(Battery.updated_at.desc())
        .limit(source_limit)
    ).all()
    for battery in low_battery_rows:
        ts = battery.updated_at or battery.created_at
        station_id = _resolve_station_id(battery)
        station_name = station_name_by_id.get(int(station_id), "Unknown station") if station_id is not None else "Unknown station"
        events.append(
            {
                "timestamp": ts,
                "title": "Battery Health Alert",
                "description": (
                    f"Battery #{battery.id} at {station_name} has charge {round(float(battery.current_charge or 0), 1)}% "
                    f"and health {round(float(battery.health_percentage or 0), 1)}%"
                ),
                "type": "alert",
            }
        )

    events.sort(key=lambda event: event["timestamp"], reverse=True)

    activities = [
        {
            "title": event["title"],
            "description": event["description"],
            "time": _time_ago(now, event["timestamp"]),
            "type": event["type"],
        }
        for event in events[:limit]
    ]

    return {"activities": activities}


@router.get("/top-stations")
async def get_dashboard_top_stations(
    limit: int = Query(5, ge=1, le=50),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    _ = current_user

    since = datetime.now(UTC) - timedelta(days=30)

    stations = db.exec(select(Station)).all()
    station_index = {int(station.id): station for station in stations if station.id is not None}

    rental_rows = db.exec(
        select(
            Rental.start_station_id,
            func.count(Rental.id),
            func.sum(Rental.total_amount),
            func.count(func.distinct(Rental.user_id)),
            func.avg(Rental.total_amount),
        )
        .where(Rental.start_time >= since)
        .group_by(Rental.start_station_id)
    ).all()
    rental_stats = {
        int(station_id): {
            "rentals": int(total_rentals or 0),
            "revenue": float(total_revenue or 0.0),
            "unique_users": int(unique_users or 0),
            "avg_ticket": round(float(avg_ticket or 0.0), 2),
        }
        for station_id, total_rentals, total_revenue, unique_users, avg_ticket in rental_rows
        if station_id is not None
    }

    active_rental_rows = db.exec(
        select(Rental.start_station_id, func.count(Rental.id))
        .where(Rental.status == "active")
        .group_by(Rental.start_station_id)
    ).all()
    active_rentals_by_station = {
        int(station_id): int(active_count or 0)
        for station_id, active_count in active_rental_rows
        if station_id is not None
    }

    # SQL GROUP BY for battery count per station (replaces loading ALL batteries)
    from sqlalchemy import case as sa_case, literal_column
    _resolved_station = func.coalesce(
        Battery.station_id,
        sa_case(
            (Battery.location_type == "station", Battery.location_id),
            else_=literal_column("NULL"),
        ),
    )
    battery_count_rows = db.exec(
        select(_resolved_station.label("sid"), func.count(Battery.id))
        .where(_resolved_station.isnot(None))
        .group_by(literal_column("sid"))
    ).all()
    battery_count_by_station: dict[int, int] = {int(r[0]): int(r[1]) for r in battery_count_rows if r[0] is not None}

    payload = []
    for station_id, station in station_index.items():
        stats = rental_stats.get(station_id, {})
        rentals = int(stats.get("rentals", 0))
        revenue = float(stats.get("revenue", 0.0))
        active_rentals = int(active_rentals_by_station.get(station_id, 0))
        battery_count = int(battery_count_by_station.get(station_id, 0))
        utilization = round((active_rentals / battery_count) * 100, 1) if battery_count > 0 else 0.0

        payload.append(
            {
                "id": str(station.id),
                "name": station.name,
                "location": station.address or station.city or "Unknown",
                "rentals": rentals,
                "revenue": round(revenue, 2),
                "utilization": utilization,
                "rating": round(float(station.rating or 0.0), 1),
                "unique_users": int(stats.get("unique_users", 0)),
                "avg_ticket_size": float(stats.get("avg_ticket", 0.0)),
            }
        )

    payload.sort(key=lambda item: (item["revenue"], item["rentals"]), reverse=True)

    return {"stations": payload[:limit]}
