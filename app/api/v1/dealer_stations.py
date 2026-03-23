"""
Dealer Station API — Endpoints for dealers to manage their stations, monitor
inventory, update rules, and schedule maintenance.
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from datetime import datetime

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.station import Station
from app.services.dealer_station_service import DealerStationService
from pydantic import BaseModel

router = APIRouter()

def _get_dealer_id(db: Session, user_id: int) -> int:
    """Resolve dealer_id from current user, or raise 403."""
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user_id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Not a dealer")
    return dealer.id


# ─── Schemas ───

class StationSubmit(BaseModel):
    name: str
    tenant_id: str | None = "default"
    address: str
    latitude: float
    longitude: float
    station_type: str = "automated"
    power_type: str = "grid"
    connectivity_type: str = "4g"
    total_slots: int
    contact_phone: str | None = None
    opening_hours: str | None = None

class RuleUpdate(BaseModel):
    low_stock_threshold_pct: float

class HoursUpdate(BaseModel):
    hours: str

class MaintenanceScheduleReq(BaseModel):
    start_time: datetime
    end_time: datetime | None = None
    reason: str


# ─── Endpoints ───

@router.post("")
def submit_station(
    data: StationSubmit,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Submit a new station. Will be pending active state."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerStationService.submit_station(db, dealer_id, data.dict())


@router.get("/{station_id}/batteries")
def get_station_batteries(
    station_id: int,
    health_status: str | None = Query(None, description="good, degraded, damaged"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """View real-time batteries at a specific station, optionally filtered by health."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerStationService.get_station_batteries(db, station_id, dealer_id, health_status)


@router.put("/{station_id}/inventory-rules")
def update_inventory_rules(
    station_id: int,
    data: RuleUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update custom low-stock threshold for a station."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerStationService.update_inventory_rules(db, station_id, dealer_id, data.low_stock_threshold_pct)


@router.put("/{station_id}/hours")
def update_opening_hours(
    station_id: int,
    data: HoursUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update operational opening hours for a station."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerStationService.update_opening_hours(db, station_id, dealer_id, data.hours)


@router.post("/{station_id}/maintenance")
def schedule_maintenance(
    station_id: int,
    data: MaintenanceScheduleReq,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Schedule future downtime for a station."""
    dealer_id = _get_dealer_id(db, current_user.id)
    downtime = DealerStationService.schedule_maintenance(db, station_id, dealer_id, data.dict())
    return downtime


@router.get("/alerts")
def fetch_inventory_alerts(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Fetch low-inventory alerts across all dealer stations based on custom thresholds."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerStationService.get_low_inventory_alerts(db, dealer_id)

