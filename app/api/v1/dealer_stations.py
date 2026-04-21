from __future__ import annotations
"""
Dealer Station API — Endpoints for dealers to manage their stations, monitor
inventory, update rules, and schedule maintenance.
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from datetime import datetime, timezone; UTC = timezone.utc

from app.db.session import get_session
from app.api import deps
from app.api.deps import get_current_user
from app.models.user import User
from app.models.station import Station, StationSlot
from app.models.rental import Rental
from app.models.maintenance import MaintenanceRecord
from app.services.dealer_station_service import DealerStationService
from pydantic import BaseModel
from app.utils.audit_context import log_audit_action
from app.models.audit_log import AuditActionType

router = APIRouter()

def _get_dealer_id(db: Session, user_id: int) -> int:
    """Resolve dealer_id from current user, or raise 403."""
    dealer = deps.get_dealer_profile_or_403(db, user_id, detail="Not a dealer")
    return dealer.id


# ─── Schemas ───

class StationSubmit(BaseModel):
    name: str
    tenant_id: str | None = "default"
    address: str
    city: str | None = None
    latitude: float
    longitude: float
    station_type: str = "automated"
    total_slots: int
    is_24x7: bool = False
    contact_phone: str | None = None
    operating_hours: str | None = None

class StationUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    contact_phone: str | None = None
    operating_hours: str | None = None
    is_24x7: bool | None = None
    total_slots: int | None = None

class RuleUpdate(BaseModel):
    low_stock_threshold_pct: float

class HoursUpdate(BaseModel):
    hours: str

class MaintenanceScheduleReq(BaseModel):
    start_time: datetime
    end_time: datetime | None = None
    reason: str


# ─── List & Detail Endpoints ───

@router.get("")
def list_stations(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List all stations belonging to the dealer."""
    dealer_id = _get_dealer_id(db, current_user.id)
    stations = db.exec(
        select(Station).where(Station.dealer_id == dealer_id)
    ).all()

    result = []
    for s in stations:
        # Count active swaps at this station
        active_rentals = 0
        try:
            active_rentals = db.exec(
                select(func.count(Rental.id)).where(
                    Rental.start_station_id == s.id,
                    Rental.status == "active",
                )
            ).one() or 0
        except Exception:
            pass

        # Slot utilization
        total_slots = s.total_slots or 1
        occupied_slots = 0
        try:
            occupied_slots = db.exec(
                select(func.count(StationSlot.id)).where(
                    StationSlot.station_id == s.id,
                    StationSlot.status.in_(["charging", "ready"]),
                )
            ).one() or 0
        except Exception:
            pass

        utilization = round((occupied_slots / total_slots) * 100, 1) if total_slots > 0 else 0

        result.append({
            "id": s.id,
            "name": s.name,
            "address": s.address,
            "city": s.city or "",
            "latitude": s.latitude,
            "longitude": s.longitude,
            "status": s.status,
            "station_type": s.station_type,
            "total_slots": s.total_slots,
            "available_batteries": s.available_batteries,
            "available_slots": s.available_slots,
            "is_24x7": s.is_24x7,
            "rating": round(s.rating, 1),
            "active_swaps": active_rentals,
            "utilization_percent": utilization,
            "contact_phone": s.contact_phone,
            "operating_hours": s.operating_hours,
            "last_maintenance_date": str(s.last_maintenance_date) if s.last_maintenance_date else None,
            "last_heartbeat": str(s.last_heartbeat) if s.last_heartbeat else None,
            "created_at": str(s.created_at),
        })

    return result


@router.get("/{station_id}")
def get_station_detail(
    station_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get detailed station info with slots, recent activity, and maintenance history."""
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(
        select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)
    ).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    # Slots
    slots = db.exec(select(StationSlot).where(StationSlot.station_id == station_id)).all()
    slot_data = [
        {
            "id": sl.id,
            "slot_number": sl.slot_number,
            "status": sl.status,
            "is_locked": sl.is_locked,
            "current_power_w": sl.current_power_w,
            "battery_id": sl.battery_id,
        }
        for sl in slots
    ]

    # Recent rentals
    recent_rentals = db.exec(
        select(Rental)
        .where(Rental.start_station_id == station_id)
        .order_by(Rental.start_time.desc())
        .limit(10)
    ).all()
    rental_data = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
            "start_time": str(r.start_time),
            "total_amount": r.total_amount,
        }
        for r in recent_rentals
    ]

    # Maintenance history
    maintenance = db.exec(
        select(MaintenanceRecord)
        .where(MaintenanceRecord.entity_type == "station", MaintenanceRecord.entity_id == station_id)
        .order_by(MaintenanceRecord.performed_at.desc())
        .limit(10)
    ).all()
    maint_data = [
        {
            "id": m.id,
            "type": m.maintenance_type,
            "description": m.description,
            "cost": m.cost,
            "status": m.status,
            "performed_at": str(m.performed_at),
        }
        for m in maintenance
    ]

    # Active rentals count
    active_rentals = db.exec(
        select(func.count(Rental.id)).where(
            Rental.start_station_id == station_id,
            Rental.status == "active",
        )
    ).one() or 0

    # Slot utilization
    total_slots = station.total_slots or 1
    occupied = len([sl for sl in slots if sl.status in ("charging", "ready")])
    utilization = round((occupied / total_slots) * 100, 1)

    return {
        "station": {
            "id": station.id,
            "name": station.name,
            "address": station.address,
            "city": station.city or "",
            "latitude": station.latitude,
            "longitude": station.longitude,
            "status": station.status,
            "station_type": station.station_type,
            "total_slots": station.total_slots,
            "available_batteries": station.available_batteries,
            "available_slots": station.available_slots,
            "is_24x7": station.is_24x7,
            "rating": round(station.rating, 1),
            "contact_phone": station.contact_phone,
            "operating_hours": station.operating_hours,
            "last_maintenance_date": str(station.last_maintenance_date) if station.last_maintenance_date else None,
            "created_at": str(station.created_at),
        },
        "active_swaps": active_rentals,
        "utilization_percent": utilization,
        "slots": slot_data,
        "recent_rentals": rental_data,
        "maintenance_history": maint_data,
    }


@router.put("/{station_id}")
def update_station(
    station_id: int,
    data: StationUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update station details."""
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(
        select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)
    ).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    update_data = data.dict(exclude_unset=True, exclude_none=True)
    for key, value in update_data.items():
        setattr(station, key, value)

    station.updated_at = datetime.now(UTC)
    db.add(station)
    
    log_audit_action(
        db=db,
        action=AuditActionType.DATA_MODIFICATION,
        level="INFO",
        resource_type="STATION",
        target_id=station.id,
        details=f"Station updated by dealer user {current_user.id}"
    )
    
    db.commit()
    db.refresh(station)
    return {"message": "Station updated", "id": station.id}
@router.get("/{station_id}/maintenance")
def get_station_maintenance(
    station_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get maintenance history for a specific station."""
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(
        select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)
    ).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    records = db.exec(
        select(MaintenanceRecord)
        .where(MaintenanceRecord.entity_type == "station", MaintenanceRecord.entity_id == station_id)
        .order_by(MaintenanceRecord.performed_at.desc())
    ).all()

    return [
        {
            "id": m.id,
            "type": m.maintenance_type,
            "description": m.description,
            "cost": m.cost,
            "status": m.status,
            "performed_at": str(m.performed_at),
        }
        for m in records
    ]


# ─── Existing Endpoints ───

@router.post("/new")
def submit_new_station(
    data: StationSubmit,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Submit a new station. Will be pending active state."""
    dealer_id = _get_dealer_id(db, current_user.id)
    result = DealerStationService.submit_station(db, dealer_id, data.dict())
    
    log_audit_action(
        db=db,
        action=AuditActionType.DATA_MODIFICATION,
        level="INFO",
        resource_type="STATION",
        target_id=result.get("id") if isinstance(result, dict) else None,
        details=f"New station submitted by dealer user {current_user.id}"
    )
    # Note: Service already commits but we add logic here and commit again (audit is pending transaction)
    db.commit()
    
    return result


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


@router.post("/{station_id}/schedule-maintenance")
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


@router.get("/inventory/alerts")
def fetch_inventory_alerts(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Fetch low-inventory alerts across all dealer stations based on custom thresholds."""
    dealer_id = _get_dealer_id(db, current_user.id)
    return DealerStationService.get_low_inventory_alerts(db, dealer_id)
# ─── Newly Added Dealer Portal Aggregation Routes ───

@router.get("/stats")
def get_dealer_quick_stats(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    # TODO: Perform actual counts
    return {
        "available_batteries": 45,
        "total_batteries": 100,
        "ongoing_rentals": 12,
        "current_swaps": 3,
        "avg_rating": 4.5,
        "station_count": 5
    }

@router.get("/batteries")
def get_dealer_batteries(
    station_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    return []

@router.get("/rentals/active")
def get_dealer_active_rentals(
    station_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    return []

@router.get("/reviews")
def get_dealer_reviews(
    station_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    return []

@router.get("/swaps/list")
def get_dealer_swaps(
    station_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    return []

@router.get("/{station_id}/activity")
def get_station_activity(
    station_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    return []

@router.get("/{station_id}/transactions")
def get_station_transactions(
    station_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    return []
