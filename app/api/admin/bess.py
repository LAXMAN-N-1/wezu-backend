from __future__ import annotations
"""BESS Admin API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime, timedelta, timezone; UTC = timezone.utc

from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User
from app.models.bess import BessUnit, BessEnergyLog, BessGridEvent, BessReport
from app.schemas.bess import (
    BessUnitRead, BessUnitCreate, BessEnergyLogRead,
    BessGridEventRead, BessGridEventCreate, BessReportRead, BessOverviewStats
)

router = APIRouter()

# ============================================================================
# Overview
# ============================================================================

@router.get("/overview", response_model=BessOverviewStats)
def get_bess_overview(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    """Aggregate dashboard stats for BESS overview."""
    units = session.exec(select(BessUnit)).all()
    if not units:
        return BessOverviewStats(
            total_units=0, online_units=0, total_capacity_kwh=0,
            current_stored_kwh=0, avg_soc=0, avg_soh=0,
            total_energy_today_kwh=0, total_revenue_today=0
        )

    total = len(units)
    online = sum(1 for u in units if u.status == "online")
    total_cap = sum(u.capacity_kwh for u in units)
    current_stored = sum(u.current_charge_kwh for u in units)
    avg_soc = sum(u.soc for u in units) / total if total else 0
    avg_soh = sum(u.soh for u in units) / total if total else 0

    # Today's energy
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = session.exec(
        select(BessEnergyLog).where(BessEnergyLog.timestamp >= today_start)
    ).all()
    total_energy = sum(abs(l.energy_kwh) for l in today_logs)

    # Today's revenue from grid events
    today_events = session.exec(
        select(BessGridEvent).where(
            BessGridEvent.start_time >= today_start,
            BessGridEvent.status == "completed"
        )
    ).all()
    total_revenue = sum(e.revenue_earned or 0 for e in today_events)

    return BessOverviewStats(
        total_units=total, online_units=online,
        total_capacity_kwh=round(total_cap, 1),
        current_stored_kwh=round(current_stored, 1),
        avg_soc=round(avg_soc, 1), avg_soh=round(avg_soh, 1),
        total_energy_today_kwh=round(total_energy, 1),
        total_revenue_today=round(total_revenue, 2)
    )


# ============================================================================
# Units
# ============================================================================

@router.get("/units", response_model=List[BessUnitRead])
def list_bess_units(
    session: Session = Depends(get_db),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin),
):
    query = select(BessUnit)
    if status:
        query = query.where(BessUnit.status == status)
    return session.exec(query.order_by(BessUnit.name)).all()


@router.get("/units/{unit_id}", response_model=BessUnitRead)
def get_bess_unit(
    unit_id: int,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    unit = session.get(BessUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="BESS unit not found")
    return unit


@router.post("/units", response_model=BessUnitRead)
def create_bess_unit(
    unit_in: BessUnitCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    unit = BessUnit.model_validate(unit_in)
    unit.installed_at = datetime.now(UTC)
    session.add(unit)
    session.commit()
    session.refresh(unit)
    return unit


# ============================================================================
# Energy Monitoring
# ============================================================================

@router.get("/energy-logs", response_model=List[BessEnergyLogRead])
def list_energy_logs(
    session: Session = Depends(get_db),
    bess_unit_id: Optional[int] = None,
    source: Optional[str] = None,
    hours: int = Query(24, description="Hours of data to fetch"),
    current_user: User = Depends(get_current_active_admin),
):
    since = datetime.now(UTC) - timedelta(hours=hours)
    query = select(BessEnergyLog).where(BessEnergyLog.timestamp >= since)
    if bess_unit_id:
        query = query.where(BessEnergyLog.bess_unit_id == bess_unit_id)
    if source:
        query = query.where(BessEnergyLog.source == source)
    return session.exec(query.order_by(BessEnergyLog.timestamp.desc()).limit(500)).all()


@router.get("/energy-logs/summary")
def energy_summary(
    session: Session = Depends(get_db),
    days: int = Query(7, description="Days to summarize"),
    current_user: User = Depends(get_current_active_admin),
):
    """Per-day energy summary for charts."""
    since = datetime.now(UTC) - timedelta(days=days)
    logs = session.exec(
        select(BessEnergyLog).where(BessEnergyLog.timestamp >= since)
    ).all()

    daily = {}
    for log in logs:
        day = log.timestamp.strftime("%Y-%m-%d")
        if day not in daily:
            daily[day] = {"charged": 0.0, "discharged": 0.0, "date": day}
        if log.power_kw >= 0:
            daily[day]["charged"] += log.energy_kwh
        else:
            daily[day]["discharged"] += abs(log.energy_kwh)

    return sorted(daily.values(), key=lambda x: x["date"])


# ============================================================================
# Grid Integration
# ============================================================================

@router.get("/grid-events", response_model=List[BessGridEventRead])
def list_grid_events(
    session: Session = Depends(get_db),
    bess_unit_id: Optional[int] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    days: int = Query(30, description="Days of history"),
    current_user: User = Depends(get_current_active_admin),
):
    since = datetime.now(UTC) - timedelta(days=days)
    query = select(BessGridEvent).where(BessGridEvent.start_time >= since)
    if bess_unit_id:
        query = query.where(BessGridEvent.bess_unit_id == bess_unit_id)
    if event_type:
        query = query.where(BessGridEvent.event_type == event_type)
    if status:
        query = query.where(BessGridEvent.status == status)
    return session.exec(query.order_by(BessGridEvent.start_time.desc())).all()


@router.post("/grid-events", response_model=BessGridEventRead)
def create_grid_event(
    event_in: BessGridEventCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    event = BessGridEvent.model_validate(event_in)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.patch("/grid-events/{event_id}")
def update_grid_event_status(
    event_id: int,
    new_status: str = Query(...),
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    event = session.get(BessGridEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Grid event not found")
    event.status = new_status
    if new_status == "completed":
        event.end_time = datetime.now(UTC)
    session.add(event)
    session.commit()
    return {"ok": True, "status": new_status}


# ============================================================================
# Reports
# ============================================================================

@router.get("/reports", response_model=List[BessReportRead])
def list_reports(
    session: Session = Depends(get_db),
    report_type: Optional[str] = None,
    bess_unit_id: Optional[int] = None,
    current_user: User = Depends(get_current_active_admin),
):
    query = select(BessReport)
    if report_type:
        query = query.where(BessReport.report_type == report_type)
    if bess_unit_id:
        query = query.where(BessReport.bess_unit_id == bess_unit_id)
    return session.exec(query.order_by(BessReport.period_end.desc())).all()


@router.get("/reports/kpi")
def reports_kpi(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
):
    """KPI summary for reports dashboard."""
    reports = session.exec(select(BessReport).order_by(BessReport.period_end.desc()).limit(30)).all()
    if not reports:
        return {"total_charged": 0, "total_discharged": 0, "avg_efficiency": 0, "total_revenue": 0, "total_cost": 0}
    return {
        "total_charged": round(sum(r.total_charged_kwh for r in reports), 1),
        "total_discharged": round(sum(r.total_discharged_kwh for r in reports), 1),
        "avg_efficiency": round(sum(r.avg_efficiency for r in reports) / len(reports), 1),
        "total_revenue": round(sum(r.revenue for r in reports), 2),
        "total_cost": round(sum(r.cost for r in reports), 2),
        "report_count": len(reports),
    }
