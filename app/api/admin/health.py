from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, col
from typing import List, Optional
from datetime import datetime, UTC, timedelta

from app.api.deps import get_db, get_current_active_admin
from app.models.battery import Battery, BatteryStatus, BatteryHealth
from app.models.battery_health import (
    BatteryHealthSnapshot, BatteryMaintenanceSchedule, BatteryHealthAlert,
    SnapshotType, MaintenanceType, MaintenancePriority, MaintenanceStatus,
    AlertType, AlertSeverity
)
from app.schemas.battery_health import (
    HealthOverviewResponse, HealthBatteryResponse, HealthBatteryDetailResponse,
    HealthSnapshotResponse, HealthSnapshotCreate,
    MaintenanceScheduleResponse, MaintenanceScheduleCreate,
    HealthAlertResponse, AlertResolveRequest,
    HealthAnalyticsResponse, FleetHealthTrendPoint, WorstDegrader
)
from sqlalchemy import case, and_
from app.core.config import settings
from app.utils.runtime_cache import cached_call, invalidate_cache
from sqlalchemy.orm import aliased

router = APIRouter()


def _parse_battery_id(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Battery ID must be an integer") from exc


def _invalidate_health_caches() -> None:
    invalidate_cache("admin-health")
    invalidate_cache("health_overview")
    invalidate_cache("health_analytics")


def _compute_bulk_degradation_rates(battery_ids: List[int], db: Session, days: int = 90) -> dict:
    if not battery_ids:
        return {}
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rates = {bid: 0.0 for bid in battery_ids}

    bounds_subquery = (
        select(
            BatteryHealthSnapshot.battery_id.label("battery_id"),
            func.min(col(BatteryHealthSnapshot.recorded_at)).label("first_recorded_at"),
            func.max(col(BatteryHealthSnapshot.recorded_at)).label("last_recorded_at"),
        )
        .where(BatteryHealthSnapshot.battery_id.in_(battery_ids))
        .where(col(BatteryHealthSnapshot.recorded_at) >= cutoff)
        .group_by(BatteryHealthSnapshot.battery_id)
        .subquery()
    )

    first_snapshot = aliased(BatteryHealthSnapshot)
    last_snapshot = aliased(BatteryHealthSnapshot)

    rows = db.exec(
        select(
            bounds_subquery.c.battery_id,
            first_snapshot.health_percentage,
            first_snapshot.recorded_at,
            last_snapshot.health_percentage,
            last_snapshot.recorded_at,
        )
        .join(
            first_snapshot,
            and_(
                first_snapshot.battery_id == bounds_subquery.c.battery_id,
                col(first_snapshot.recorded_at) == bounds_subquery.c.first_recorded_at,
            ),
        )
        .join(
            last_snapshot,
            and_(
                last_snapshot.battery_id == bounds_subquery.c.battery_id,
                col(last_snapshot.recorded_at) == bounds_subquery.c.last_recorded_at,
            ),
        )
    ).all()

    for row in rows:
        bid = row[0]
        first_health = row[1]
        first_recorded_at = _coerce_datetime(row[2])
        last_health = row[3]
        last_recorded_at = _coerce_datetime(row[4])

        if not first_recorded_at or not last_recorded_at:
            continue

        elapsed_days = (last_recorded_at - first_recorded_at).total_seconds() / 86400
        if elapsed_days <= 0:
            continue

        drop = float(first_health or 0) - float(last_health or 0)
        if drop <= 0:
            continue

        rates[bid] = round((drop / elapsed_days) * 30, 2)

    return rates

def _compute_degradation_rate(battery_id: int, db: Session, days: int = 90) -> float:
    return _compute_bulk_degradation_rates([battery_id], db, days).get(battery_id, 0.0)

def _get_health_status(health: float) -> str:
    if health > 80:
        return "good"
    elif health > 50:
        return "fair"
    elif health > 30:
        return "poor"
    else:
        return "critical"

def _get_health_enum(health: float) -> BatteryHealth:
    if health > 80:
        return BatteryHealth.GOOD
    elif health > 50:
        return BatteryHealth.FAIR
    elif health > 30:
        return BatteryHealth.POOR
    else:
        return BatteryHealth.CRITICAL

def _coerce_datetime(value: object) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _serialize_dt(dt: Optional[datetime]) -> Optional[str]:
    normalized = _coerce_datetime(dt)
    return normalized.isoformat() if normalized else None


def _latest_snapshots_by_battery(
    battery_ids: List[int], db: Session
) -> dict[int, BatteryHealthSnapshot]:
    if not battery_ids:
        return {}

    latest_snapshot_subquery = (
        select(
            BatteryHealthSnapshot.battery_id.label("battery_id"),
            func.max(col(BatteryHealthSnapshot.recorded_at)).label("latest_recorded_at"),
        )
        .where(BatteryHealthSnapshot.battery_id.in_(battery_ids))
        .group_by(BatteryHealthSnapshot.battery_id)
        .subquery()
    )

    snapshots = db.exec(
        select(BatteryHealthSnapshot)
        .join(
            latest_snapshot_subquery,
            and_(
                BatteryHealthSnapshot.battery_id == latest_snapshot_subquery.c.battery_id,
                col(BatteryHealthSnapshot.recorded_at) == latest_snapshot_subquery.c.latest_recorded_at,
            ),
        )
    ).all()

    snapshot_map: dict[int, BatteryHealthSnapshot] = {}
    for snapshot in snapshots:
        if snapshot.battery_id not in snapshot_map:
            snapshot_map[snapshot.battery_id] = snapshot
    return snapshot_map


def _latest_completed_maintenance_by_battery(
    battery_ids: List[int], db: Session
) -> dict[int, BatteryMaintenanceSchedule]:
    if not battery_ids:
        return {}

    latest_maintenance_subquery = (
        select(
            BatteryMaintenanceSchedule.battery_id.label("battery_id"),
            func.max(col(BatteryMaintenanceSchedule.completed_at)).label("latest_completed_at"),
        )
        .where(BatteryMaintenanceSchedule.battery_id.in_(battery_ids))
        .where(BatteryMaintenanceSchedule.status == MaintenanceStatus.COMPLETED)
        .where(BatteryMaintenanceSchedule.completed_at.is_not(None))
        .group_by(BatteryMaintenanceSchedule.battery_id)
        .subquery()
    )

    maintenance_rows = db.exec(
        select(BatteryMaintenanceSchedule)
        .join(
            latest_maintenance_subquery,
            and_(
                BatteryMaintenanceSchedule.battery_id == latest_maintenance_subquery.c.battery_id,
                col(BatteryMaintenanceSchedule.completed_at) == latest_maintenance_subquery.c.latest_completed_at,
            ),
        )
    ).all()

    maintenance_map: dict[int, BatteryMaintenanceSchedule] = {}
    for maintenance in maintenance_rows:
        if maintenance.battery_id not in maintenance_map:
            maintenance_map[maintenance.battery_id] = maintenance
    return maintenance_map

# ============================================================
# GET /health/overview — Fleet-wide health summary
# ============================================================
@router.get("/overview", response_model=HealthOverviewResponse)
def get_health_overview(db: Session = Depends(get_db)):
    def _fetch():
        # SQL-side aggregation instead of loading all batteries
        row = db.exec(
            select(
                func.count(Battery.id).label("total"),
                func.coalesce(func.avg(Battery.health_percentage), 0).label("avg_health"),
                func.coalesce(func.sum(case((Battery.health_percentage > 80, 1), else_=0)), 0).label("good"),
                func.coalesce(func.sum(case((and_(Battery.health_percentage > 50, Battery.health_percentage <= 80), 1), else_=0)), 0).label("fair"),
                func.coalesce(func.sum(case((and_(Battery.health_percentage > 30, Battery.health_percentage <= 50), 1), else_=0)), 0).label("poor"),
                func.coalesce(func.sum(case((Battery.health_percentage <= 30, 1), else_=0)), 0).label("critical"),
            )
        ).one()
        total = row.total or 0
        if total == 0:
            return HealthOverviewResponse(
                fleet_avg_health=0, good_count=0, fair_count=0, poor_count=0,
                critical_count=0, avg_degradation_rate=0, batteries_needing_service=0,
                scheduled_maintenance_count=0, total_batteries=0
            ).model_dump()

        # Bulk degradation rates still need snapshots — keep existing logic but only fetch IDs
        b_ids = list(db.exec(select(Battery.id)).all())
        rates_90d = _compute_bulk_degradation_rates(b_ids, db, days=90)
        rates_30d = _compute_bulk_degradation_rates(b_ids, db, days=30)

        degs = [r for r in rates_90d.values() if r > 0]
        avg_deg = round(sum(degs) / len(degs), 2) if degs else 0.0
        needing_service = sum(1 for bid, r in rates_30d.items() if r > 5)

        next_week = datetime.now(UTC) + timedelta(days=7)
        upcoming = db.exec(
            select(func.count(BatteryMaintenanceSchedule.id))
            .where(BatteryMaintenanceSchedule.status == MaintenanceStatus.SCHEDULED)
            .where(BatteryMaintenanceSchedule.scheduled_date <= next_week)
        ).first() or 0

        return HealthOverviewResponse(
            fleet_avg_health=round(float(row.avg_health), 1),
            good_count=row.good,
            fair_count=row.fair,
            poor_count=row.poor,
            critical_count=row.critical,
            avg_degradation_rate=avg_deg,
            batteries_needing_service=needing_service,
            scheduled_maintenance_count=upcoming,
            total_batteries=total
        ).model_dump()
    return cached_call("health_overview", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)

# ============================================================
# GET /health/batteries — Paginated list with filters
# ============================================================
@router.get("/batteries", response_model=List[HealthBatteryResponse])
def get_health_batteries(
    health_range: Optional[str] = Query(None, description="good/fair/poor/critical"),
    sort_by: Optional[str] = Query("health_desc", description="health_asc/health_desc/degradation_rate/last_service"),
    needs_attention: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cache_sort = sort_by or "health_desc"
    cache_search = (search or "").strip().lower()
    cache_needs_attention = "none" if needs_attention is None else str(needs_attention).lower()

    def _load() -> list[dict]:
        # ── 1. Build base query with SQL-level filters ──────────────────
        query = select(Battery)
        if search:
            query = query.where(Battery.serial_number.ilike(f"%{search}%"))

        # Apply health_range filter at SQL level
        if health_range == "good":
            query = query.where(Battery.health_percentage > 80)
        elif health_range == "fair":
            query = query.where(and_(Battery.health_percentage > 50, Battery.health_percentage <= 80))
        elif health_range == "poor":
            query = query.where(and_(Battery.health_percentage > 30, Battery.health_percentage <= 50))
        elif health_range == "critical":
            query = query.where(Battery.health_percentage <= 30)

        # ── 2. Determine if we can use SQL pagination ───────────────────
        # degradation_rate and needs_attention require post-fetch filtering,
        # so we only use SQL pagination for simple health sorts.
        can_sql_paginate = not needs_attention and sort_by in ("health_asc", "health_desc", None)

        if can_sql_paginate:
            # SQL-level sort + paginate — avoids loading all batteries
            if sort_by == "health_asc":
                query = query.order_by(Battery.health_percentage.asc())
            else:
                query = query.order_by(Battery.health_percentage.desc())

            offset = (page - 1) * limit
            batteries = db.exec(query.offset(offset).limit(limit)).all()
        else:
            # Must load all for post-processing sorts / filters
            batteries = db.exec(query).all()

        if not batteries:
            return []

        # ── 3. Bulk fetch related data only for batteries in scope ──────
        b_ids = [b.id for b in batteries]
        rates = _compute_bulk_degradation_rates(b_ids, db)
        snaps_map = _latest_snapshots_by_battery(b_ids, db)
        maint_map = _latest_completed_maintenance_by_battery(b_ids, db)

        # ── 4. Build response list ──────────────────────────────────────
        results: list[dict] = []
        now = datetime.now(UTC)

        for b in batteries:
            health = b.health_percentage
            status = _get_health_status(health)
            deg_rate = rates.get(b.id, 0.0)

            # Post-filter: needs_attention (only when can't SQL paginate)
            if needs_attention and health >= 60 and deg_rate <= 3:
                continue

            latest = snaps_map.get(b.id)
            last_maint = maint_map.get(b.id)

            days_since = None
            completed_at = _coerce_datetime(last_maint.completed_at) if last_maint else None
            if completed_at:
                days_since = (now - completed_at).days

            results.append({
                "id": str(b.id),
                "serial_number": b.serial_number,
                "manufacturer": b.manufacturer,
                "battery_type": b.battery_type,
                "status": b.status.value if hasattr(b.status, "value") else str(b.status),
                "health_percentage": health,
                "health_status": status,
                "voltage": latest.voltage if latest else None,
                "temperature": latest.temperature if latest else None,
                "internal_resistance": latest.internal_resistance if latest else None,
                "charge_cycles": latest.charge_cycles if latest else None,
                "degradation_rate": deg_rate,
                "last_reading_at": _serialize_dt(latest.recorded_at) if latest else None,
                "last_maintenance_at": _serialize_dt(last_maint.completed_at) if last_maint else None,
                "days_since_maintenance": days_since,
            })

        # ── 5. Post-processing sort + paginate (only when needed) ───────
        if not can_sql_paginate:
            if sort_by == "health_asc":
                results.sort(key=lambda x: x["health_percentage"])
            elif sort_by == "health_desc":
                results.sort(key=lambda x: x["health_percentage"], reverse=True)
            elif sort_by == "degradation_rate":
                results.sort(key=lambda x: x["degradation_rate"], reverse=True)
            elif sort_by == "last_service":
                results.sort(key=lambda x: x["days_since_maintenance"] or 9999, reverse=True)

            start = (page - 1) * limit
            results = results[start:start + limit]

        return results

    return cached_call(
        "admin-health",
        "batteries",
        health_range or "",
        cache_sort,
        cache_needs_attention,
        cache_search,
        page,
        limit,
        ttl_seconds=min(settings.ANALYTICS_CACHE_TTL_SECONDS, 60),
        call=_load,
    )


# ============================================================
# GET /health/batteries/{battery_id} — Full detail profile
# ============================================================
@router.get("/batteries/{battery_id}", response_model=HealthBatteryDetailResponse)
def get_health_battery_detail(battery_id: int, db: Session = Depends(get_db)):
    bid = battery_id
    battery = db.exec(select(Battery).where(Battery.id == bid)).first()
    if not battery:
        raise HTTPException(404, "Battery not found")

    # All snapshots sorted oldest→newest
    snapshots = db.exec(
        select(BatteryHealthSnapshot)
        .where(BatteryHealthSnapshot.battery_id == bid)
        .order_by(col(BatteryHealthSnapshot.recorded_at).asc())
    ).all()

    latest = snapshots[-1] if snapshots else None

    # Degradation rate
    deg_rate = _compute_degradation_rate(bid, db)

    # Predict EOL
    predicted_eol = None
    predicted_fair = None
    if deg_rate > 0:
        health_now = battery.health_percentage
        months_to_eol = (health_now - 20) / deg_rate
        months_to_fair = (health_now - 50) / deg_rate if health_now > 50 else 0
        if months_to_eol > 0:
            predicted_eol = _serialize_dt(datetime.now(UTC) + timedelta(days=months_to_eol * 30))
        if months_to_fair > 0:
            predicted_fair = _serialize_dt(datetime.now(UTC) + timedelta(days=months_to_fair * 30))

    # Health breakdown factors
    voltage_health = min(100, max(0, (latest.voltage - 44) / 8 * 100)) if latest and latest.voltage else 90
    temp_health = min(100, max(0, 100 - max(0, (latest.temperature - 35) * 3))) if latest and latest.temperature else 90
    resist_health = min(100, max(0, 100 - (latest.internal_resistance - 10) * 2)) if latest and latest.internal_resistance else 90
    total_max_cycles = 2000
    used = latest.charge_cycles if latest and latest.charge_cycles else battery.total_cycles
    cycle_health = min(100, max(0, (1 - used / total_max_cycles) * 100))

    # Remaining cycles / years
    remaining_cycles = max(0, total_max_cycles - used)
    avg_cycles_per_month = used / 24 if used else 10  # rough est
    remaining_years = round(remaining_cycles / (avg_cycles_per_month * 12), 1) if avg_cycles_per_month > 0 else None

    # Stats
    healths = [s.health_percentage for s in snapshots]
    min_h = min(healths) if healths else None
    max_h = max(healths) if healths else None
    avg_h = round(sum(healths) / len(healths), 1) if healths else None

    # Fastest single-week drop
    fastest_drop = 0
    fastest_week = None
    for i in range(1, len(snapshots)):
        drop = snapshots[i - 1].health_percentage - snapshots[i].health_percentage
        if drop > fastest_drop:
            fastest_drop = round(drop, 1)
            fastest_week = _serialize_dt(snapshots[i].recorded_at)

    # Maintenance history
    maint_list = db.exec(
        select(BatteryMaintenanceSchedule)
        .where(BatteryMaintenanceSchedule.battery_id == bid)
        .order_by(BatteryMaintenanceSchedule.scheduled_date.desc())
    ).all()

    last_completed = next((m for m in maint_list if m.status == MaintenanceStatus.COMPLETED), None)

    # Active alerts
    alerts = db.exec(
        select(BatteryHealthAlert)
        .where(BatteryHealthAlert.battery_id == bid)
        .where(BatteryHealthAlert.is_resolved == False)
        .order_by(BatteryHealthAlert.created_at.desc())
    ).all()

    return HealthBatteryDetailResponse(
        id=str(battery.id),
        serial_number=battery.serial_number,
        manufacturer=battery.manufacturer,
        battery_type=battery.battery_type,
        status=battery.status.value if hasattr(battery.status, 'value') else str(battery.status),
        health_percentage=battery.health_percentage,
        health_status=_get_health_status(battery.health_percentage),
        voltage=latest.voltage if latest else None,
        temperature=latest.temperature if latest else None,
        internal_resistance=latest.internal_resistance if latest else None,
        charge_cycles=latest.charge_cycles if latest else None,
        total_cycles=battery.total_cycles,
        cycle_count=battery.cycle_count,
        degradation_rate=deg_rate,
        predicted_eol_date=predicted_eol,
        predicted_fair_date=predicted_fair,
        estimated_remaining_cycles=remaining_cycles,
        estimated_remaining_years=remaining_years,
        voltage_health=round(voltage_health, 1),
        temperature_health=round(temp_health, 1),
        resistance_health=round(resist_health, 1),
        cycle_health=round(cycle_health, 1),
        snapshots=[
            HealthSnapshotResponse(
                id=s.id, health_percentage=s.health_percentage,
                voltage=s.voltage, temperature=s.temperature,
                internal_resistance=s.internal_resistance, charge_cycles=s.charge_cycles,
                snapshot_type=s.snapshot_type.value, recorded_at=_serialize_dt(s.recorded_at)
            ) for s in snapshots
        ],
        maintenance_history=[
            MaintenanceScheduleResponse(
                id=m.id, battery_id=str(m.battery_id), scheduled_date=_serialize_dt(m.scheduled_date),
                maintenance_type=m.maintenance_type.value, priority=m.priority.value,
                assigned_to=m.assigned_to, status=m.status.value, notes=m.notes,
                health_before=m.health_before, health_after=m.health_after,
                completed_at=_serialize_dt(m.completed_at), created_at=_serialize_dt(m.created_at)
            ) for m in maint_list
        ],
        active_alerts=[
            HealthAlertResponse(
                id=a.id, battery_id=str(a.battery_id), alert_type=a.alert_type.value,
                severity=a.severity.value, message=a.message, is_resolved=a.is_resolved,
                resolved_by=a.resolved_by, resolved_at=_serialize_dt(a.resolved_at),
                resolution_reason=a.resolution_reason, created_at=_serialize_dt(a.created_at)
            ) for a in alerts
        ],
        min_health=min_h, max_health=max_h, avg_health=avg_h,
        fastest_drop=fastest_drop, fastest_drop_week=fastest_week,
        warranty_expiry=_serialize_dt(battery.warranty_expiry),
        last_maintenance_at=_serialize_dt(last_completed.completed_at) if last_completed else None,
        created_at=_serialize_dt(battery.created_at),
    )


# ============================================================
# GET /health/batteries/{battery_id}/snapshots
# ============================================================
@router.get("/batteries/{battery_id}/snapshots", response_model=List[HealthSnapshotResponse])
def get_battery_snapshots(
    battery_id: int,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    bid = battery_id
    cutoff = datetime.now(UTC) - timedelta(days=days)
    snapshots = db.exec(
        select(BatteryHealthSnapshot)
        .where(BatteryHealthSnapshot.battery_id == bid)
        .where(col(BatteryHealthSnapshot.recorded_at) >= cutoff)
        .order_by(col(BatteryHealthSnapshot.recorded_at).asc())
    ).all()

    return [
        HealthSnapshotResponse(
            id=s.id, health_percentage=s.health_percentage,
            voltage=s.voltage, temperature=s.temperature,
            internal_resistance=s.internal_resistance, charge_cycles=s.charge_cycles,
            snapshot_type=s.snapshot_type.value, recorded_at=_serialize_dt(s.recorded_at)
        ) for s in snapshots
    ]


# ============================================================
# POST /health/batteries/{battery_id}/snapshot
# ============================================================
@router.post("/batteries/{battery_id}/snapshot", response_model=HealthSnapshotResponse)
def record_health_snapshot(
    battery_id: int,
    data: HealthSnapshotCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_active_admin),
):
    bid = battery_id
    battery = db.exec(select(Battery).where(Battery.id == bid)).first()
    if not battery:
        raise HTTPException(404, "Battery not found")

    # Get previous reading
    prev_query = (
        select(BatteryHealthSnapshot)
        .where(BatteryHealthSnapshot.battery_id == bid)
        .order_by(col(BatteryHealthSnapshot.recorded_at).desc())
    )
    prev = db.exec(prev_query).first()

    snapshot = BatteryHealthSnapshot(
        battery_id=bid,
        health_percentage=data.health_percentage,
        voltage=data.voltage,
        temperature=data.temperature,
        internal_resistance=data.internal_resistance,
        charge_cycles=battery.total_cycles,
        snapshot_type=SnapshotType.MANUAL,
        recorded_by=admin_user.id,
    )
    db.add(snapshot)

    # Update battery health
    old_health = battery.health_percentage
    battery.health_percentage = data.health_percentage
    battery.health_status = _get_health_enum(data.health_percentage)
    battery.last_inspected_at = datetime.now(UTC)
    db.add(battery)

    # Auto-create alert if significant drop
    if prev and (prev.health_percentage - data.health_percentage) > 5:
        alert = BatteryHealthAlert(
            battery_id=bid,
            alert_type=AlertType.RAPID_DEGRADATION,
            severity=AlertSeverity.WARNING if data.health_percentage > 30 else AlertSeverity.CRITICAL,
            message=f"Health dropped {round(prev.health_percentage - data.health_percentage, 1)}% since last reading ({round(prev.health_percentage, 1)}% → {round(data.health_percentage, 1)}%)"
        )
        db.add(alert)

    if data.health_percentage <= 30:
        alert = BatteryHealthAlert(
            battery_id=bid,
            alert_type=AlertType.CRITICAL_HEALTH,
            severity=AlertSeverity.CRITICAL,
            message=f"Battery health critically low at {data.health_percentage}%"
        )
        db.add(alert)

    db.commit()
    db.refresh(snapshot)
    _invalidate_health_caches()

    return HealthSnapshotResponse(
        id=snapshot.id, health_percentage=snapshot.health_percentage,
        voltage=snapshot.voltage, temperature=snapshot.temperature,
        internal_resistance=snapshot.internal_resistance, charge_cycles=snapshot.charge_cycles,
        snapshot_type=snapshot.snapshot_type.value, recorded_at=_serialize_dt(snapshot.recorded_at)
    )


# ============================================================
# GET /health/alerts
# ============================================================
@router.get("/alerts", response_model=List[HealthAlertResponse])
def get_health_alerts(
    severity: Optional[str] = Query(None),
    battery_id: Optional[int] = Query(None),
    alert_type: Optional[str] = Query(None),
    include_resolved: bool = Query(False),
    db: Session = Depends(get_db),
):
    query = select(BatteryHealthAlert)

    if not include_resolved:
        query = query.where(BatteryHealthAlert.is_resolved == False)
    if severity:
        query = query.where(BatteryHealthAlert.severity == severity)
    if battery_id:
        query = query.where(BatteryHealthAlert.battery_id == battery_id)
    if alert_type:
        query = query.where(BatteryHealthAlert.alert_type == alert_type)

    query = query.order_by(BatteryHealthAlert.created_at.desc())
    alerts = db.exec(query).all()

    # Enrich with battery serial
    b_ids = {a.battery_id for a in alerts if a.battery_id}
    b_map = {b.id: b.serial_number for b in db.exec(select(Battery).where(Battery.id.in_(b_ids))).all()} if b_ids else {}

    result = []
    for a in alerts:
        serial = b_map.get(a.battery_id)
        result.append(HealthAlertResponse(
            id=a.id, battery_id=str(a.battery_id),
            battery_serial=serial,
            alert_type=a.alert_type.value, severity=a.severity.value,
            message=a.message, is_resolved=a.is_resolved,
            resolved_by=a.resolved_by, resolved_at=_serialize_dt(a.resolved_at),
            resolution_reason=a.resolution_reason,
            created_at=_serialize_dt(a.created_at)
        ))

    return result


# ============================================================
# POST /health/alerts/{alert_id}/resolve
# ============================================================
@router.post("/alerts/{alert_id}/resolve")
def resolve_health_alert(
    alert_id: int,
    data: AlertResolveRequest,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_active_admin),
):
    alert = db.get(BatteryHealthAlert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")

    alert.is_resolved = True
    alert.resolved_by = admin_user.id
    alert.resolved_at = datetime.now(UTC)
    alert.resolution_reason = data.reason
    db.add(alert)
    db.commit()
    _invalidate_health_caches()

    return {"status": "success", "message": "Alert resolved"}


# ============================================================
# POST /health/maintenance
# ============================================================
@router.post("/maintenance", response_model=MaintenanceScheduleResponse)
def schedule_maintenance(
    data: MaintenanceScheduleCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(get_current_active_admin),
):
    bid = _parse_battery_id(data.battery_id)
    battery = db.exec(select(Battery).where(Battery.id == bid)).first()
    if not battery:
        raise HTTPException(404, "Battery not found")

    sched = BatteryMaintenanceSchedule(
        battery_id=bid,
        scheduled_date=datetime.fromisoformat(data.scheduled_date),
        maintenance_type=MaintenanceType(data.maintenance_type),
        priority=MaintenancePriority(data.priority),
        assigned_to=data.assigned_to,
        status=MaintenanceStatus.SCHEDULED,
        notes=data.notes,
        created_by=admin_user.id,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    _invalidate_health_caches()

    return MaintenanceScheduleResponse(
        id=sched.id, battery_id=str(sched.battery_id),
        battery_serial=battery.serial_number,
        scheduled_date=_serialize_dt(sched.scheduled_date),
        maintenance_type=sched.maintenance_type.value, priority=sched.priority.value,
        assigned_to=sched.assigned_to, status=sched.status.value,
        notes=sched.notes, health_before=sched.health_before, health_after=sched.health_after,
        completed_at=_serialize_dt(sched.completed_at), created_at=_serialize_dt(sched.created_at)
    )


# ============================================================
# GET /health/maintenance
# ============================================================
@router.get("/maintenance", response_model=List[MaintenanceScheduleResponse])
def get_maintenance_list(
    status: Optional[str] = Query(None),
    upcoming_days: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = select(BatteryMaintenanceSchedule)

    if status:
        query = query.where(BatteryMaintenanceSchedule.status == MaintenanceStatus(status))
    if upcoming_days:
        cutoff = datetime.now(UTC) + timedelta(days=upcoming_days)
        query = query.where(BatteryMaintenanceSchedule.scheduled_date <= cutoff)
        query = query.where(BatteryMaintenanceSchedule.status == MaintenanceStatus.SCHEDULED)

    query = query.order_by(BatteryMaintenanceSchedule.scheduled_date.desc())
    items = db.exec(query).all()

    b_ids = {m.battery_id for m in items if m.battery_id}
    b_map = {b.id: b.serial_number for b in db.exec(select(Battery).where(Battery.id.in_(b_ids))).all()} if b_ids else {}

    result = []
    for m in items:
        serial = b_map.get(m.battery_id)
        result.append(MaintenanceScheduleResponse(
            id=m.id, battery_id=str(m.battery_id),
            battery_serial=serial,
            scheduled_date=_serialize_dt(m.scheduled_date),
            maintenance_type=m.maintenance_type.value, priority=m.priority.value,
            assigned_to=m.assigned_to, status=m.status.value,
            notes=m.notes, health_before=m.health_before, health_after=m.health_after,
            completed_at=_serialize_dt(m.completed_at), created_at=_serialize_dt(m.created_at)
        ))

    return result


# ============================================================
# GET /health/analytics — Fleet analytics
# ============================================================
@router.get("/analytics", response_model=HealthAnalyticsResponse)
def get_health_analytics(db: Session = Depends(get_db)):
    def _fetch():
        now = datetime.now(UTC)
        start_of_90d = now - timedelta(days=90)

        # 1. Fleet trend — weekly avg via SQL group_by week
        all_snaps = db.exec(
            select(BatteryHealthSnapshot)
            .where(col(BatteryHealthSnapshot.recorded_at) >= start_of_90d)
        ).all()
        normalized_snaps = []
        for snapshot in all_snaps:
            recorded_at = _coerce_datetime(snapshot.recorded_at)
            if recorded_at:
                normalized_snaps.append((snapshot, recorded_at))

        trend = []
        for week_back in range(12, -1, -1):
            week_start = now - timedelta(weeks=week_back + 1)
            week_end = now - timedelta(weeks=week_back)

            week_snaps = [
                snapshot for snapshot, recorded_at in normalized_snaps
                if week_start <= recorded_at < week_end
            ]

            if week_snaps:
                avg = round(sum(s.health_percentage for s in week_snaps) / len(week_snaps), 1)
            else:
                avg = 0

            trend.append(FleetHealthTrendPoint(
                date=week_end.strftime("%Y-%m-%d"),
                avg_health=avg
            ))

        # 2. Health distribution — SQL CASE instead of loading all batteries
        dist_row = db.exec(
            select(
                func.coalesce(func.sum(case((Battery.health_percentage > 80, 1), else_=0)), 0).label("good"),
                func.coalesce(func.sum(case((and_(Battery.health_percentage > 50, Battery.health_percentage <= 80), 1), else_=0)), 0).label("fair"),
                func.coalesce(func.sum(case((and_(Battery.health_percentage > 30, Battery.health_percentage <= 50), 1), else_=0)), 0).label("poor"),
                func.coalesce(func.sum(case((Battery.health_percentage <= 30, 1), else_=0)), 0).label("critical"),
            )
        ).one()
        distribution = {
            "good": dist_row.good,
            "fair": dist_row.fair,
            "poor": dist_row.poor,
            "critical": dist_row.critical,
        }

        # 3. Top 5 worst degraders — computed purely in SQL
        thirty_days_ago = now - timedelta(days=30)
        
        # Subquery for the first reading in last 30 days
        first_readings = (
            select(
                BatteryHealthSnapshot.battery_id,
                func.min(col(BatteryHealthSnapshot.recorded_at)).label("first_time")
            )
            .where(col(BatteryHealthSnapshot.recorded_at) >= thirty_days_ago)
            .group_by(BatteryHealthSnapshot.battery_id)
            .subquery()
        )
        
        # Subquery for the last reading in last 30 days
        last_readings = (
            select(
                BatteryHealthSnapshot.battery_id,
                func.max(col(BatteryHealthSnapshot.recorded_at)).label("last_time")
            )
            .where(col(BatteryHealthSnapshot.recorded_at) >= thirty_days_ago)
            .group_by(BatteryHealthSnapshot.battery_id)
            .subquery()
        )

        s1 = aliased(BatteryHealthSnapshot)
        s2 = aliased(BatteryHealthSnapshot)

        # Get the drop between first and last reading, filtered for top 5 drops
        degraders_query = (
            select(
                Battery.id,
                Battery.serial_number,
                Battery.health_percentage,
                (s1.health_percentage - s2.health_percentage).label("drop_amount")
            )
            .select_from(Battery)
            .join(first_readings, Battery.id == first_readings.c.battery_id)
            .join(s1, and_(s1.battery_id == Battery.id, s1.recorded_at == first_readings.c.first_time))
            .join(last_readings, Battery.id == last_readings.c.battery_id)
            .join(s2, and_(s2.battery_id == Battery.id, s2.recorded_at == last_readings.c.last_time))
            .where((s1.health_percentage - s2.health_percentage) > 0)
            .order_by((s1.health_percentage - s2.health_percentage).desc())
            .limit(5)
        )
        
        worst_rows = db.exec(degraders_query).all()
        top5 = [
            WorstDegrader(
                battery_id=str(r.id),
                serial_number=r.serial_number,
                degradation_rate=round(float(r.drop_amount), 2),
                current_health=r.health_percentage
            ) for r in worst_rows
        ]

        # 4. Maintenance compliance — 2 queries → 1 CASE
        maint_row = db.exec(
            select(
                func.count(BatteryMaintenanceSchedule.id).label("total"),
                func.coalesce(func.sum(case(
                    (BatteryMaintenanceSchedule.status == MaintenanceStatus.COMPLETED, 1), else_=0
                )), 0).label("completed"),
            )
        ).one()
        total_sched = maint_row.total or 0
        completed_on_time = maint_row.completed or 0
        compliance = round((completed_on_time / total_sched * 100), 1) if total_sched > 0 else 100.0

        return HealthAnalyticsResponse(
            fleet_trend=trend,
            health_distribution=distribution,
            worst_degraders=top5,
            maintenance_compliance_rate=compliance
        ).model_dump()
    return cached_call("health_analytics", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_fetch)
