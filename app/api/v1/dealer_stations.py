from __future__ import annotations
"""
Dealer Station API — Endpoints for dealers to manage their stations, monitor
inventory, update rules, and schedule maintenance.
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from datetime import datetime, timezone; UTC = timezone.utc
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from app.db.session import get_session
from app.api import deps
from app.api.deps import get_current_user
from app.models.user import User
from app.models.station import Station, StationSlot
from app.models.rental import Rental
from app.models.maintenance import MaintenanceRecord
from app.models.battery import Battery
from app.models.review import Review
from app.models.swap import SwapSession
from app.models.financial import Transaction
from app.services.dealer_station_service import DealerStationService
from pydantic import BaseModel
from app.utils.audit_context import log_audit_action
from app.models.audit_log import AuditActionType

router = APIRouter()

def _get_dealer_id(db: Session, user_id: int) -> int:
    """Resolve dealer_id from current user, or raise 403."""
    dealer = deps.get_dealer_profile_or_403(db, user_id, detail="Not a dealer")
    return dealer.id


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    return value.value if hasattr(value, "value") else str(value)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _user_display_name(user: User | None) -> str:
    if user is None:
        return "Customer"
    if user.full_name and user.full_name.strip():
        return user.full_name.strip()
    if user.email and "@" in user.email:
        return user.email.split("@")[0]
    if user.phone_number:
        return user.phone_number
    return f"User {user.id}"


def _dealer_station_ids(db: Session, dealer_id: int) -> list[int]:
    return list(db.exec(select(Station.id).where(Station.dealer_id == dealer_id)).all())


def _assert_station_scope(db: Session, dealer_id: int, station_id: int) -> None:
    exists = db.exec(
        select(Station.id).where(
            Station.id == station_id,
            Station.dealer_id == dealer_id,
        )
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Station not found")


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


class ReviewReplyReq(BaseModel):
    reply_text: str


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

# ─── Dealer Portal Aggregation Routes ───

@router.get("/stats")
def get_dealer_quick_stats(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    station_ids = _dealer_station_ids(db, dealer_id)
    station_count = len(station_ids)
    avg_rating = db.exec(
        select(func.coalesce(func.avg(Station.rating), 0.0)).where(Station.dealer_id == dealer_id)
    ).one() or 0.0

    if not station_ids:
        return {
            "available_batteries": 0,
            "total_batteries": 0,
            "ongoing_rentals": 0,
            "current_swaps": 0,
            "avg_rating": float(avg_rating),
            "station_count": 0,
        }

    total_batteries = db.exec(
        select(func.count(Battery.id)).where(Battery.station_id.in_(station_ids))
    ).one() or 0
    available_batteries = db.exec(
        select(func.count(Battery.id)).where(
            Battery.station_id.in_(station_ids),
            Battery.status.in_(["available", "ready"]),
        )
    ).one() or 0
    ongoing_rentals = db.exec(
        select(func.count(Rental.id)).where(
            Rental.start_station_id.in_(station_ids),
            Rental.status.in_(["active", "overdue"]),
        )
    ).one() or 0
    current_swaps = db.exec(
        select(func.count(SwapSession.id)).where(
            SwapSession.station_id.in_(station_ids),
            SwapSession.status.in_(["initiated", "processing", "in_progress", "active"]),
        )
    ).one() or 0

    return {
        "available_batteries": int(available_batteries),
        "total_batteries": int(total_batteries),
        "ongoing_rentals": int(ongoing_rentals),
        "current_swaps": int(current_swaps),
        "avg_rating": float(avg_rating),
        "station_count": int(station_count),
    }


@router.get("/batteries")
def get_dealer_batteries(
    station_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    if station_id is not None:
        _assert_station_scope(db, dealer_id, station_id)

    query = (
        select(Battery, Station)
        .join(Station, Battery.station_id == Station.id)
        .where(Station.dealer_id == dealer_id)
    )
    if station_id is not None:
        query = query.where(Station.id == station_id)
    rows = db.exec(query.order_by(Battery.updated_at.desc())).all()
    if not rows:
        return []

    battery_ids = [b.id for b, _ in rows if b.id is not None]
    active_by_battery: dict[int, tuple[Rental, User]] = {}
    latest_by_battery: dict[int, Rental] = {}
    if battery_ids:
        active_rows = db.exec(
            select(Rental, User)
            .join(User, User.id == Rental.user_id)
            .where(
                Rental.battery_id.in_(battery_ids),
                Rental.status.in_(["active", "overdue"]),
            )
        ).all()
        for rental, user in active_rows:
            if rental.battery_id is not None:
                active_by_battery[rental.battery_id] = (rental, user)

        rental_rows = db.exec(
            select(Rental)
            .where(Rental.battery_id.in_(battery_ids))
            .order_by(Rental.start_time.desc())
        ).all()
        for rental in rental_rows:
            if rental.battery_id is not None and rental.battery_id not in latest_by_battery:
                latest_by_battery[rental.battery_id] = rental

    now = datetime.now(UTC)
    payload: list[dict[str, Any]] = []
    for battery, station in rows:
        bid = battery.id or 0
        active_tuple = active_by_battery.get(bid)
        latest_rental = latest_by_battery.get(bid)

        current_customer = None
        rental_start_time = None
        if active_tuple:
            active_rental, active_user = active_tuple
            current_customer = _user_display_name(active_user)
            rental_start_time = _iso(_as_utc(active_rental.start_time))

        last_rental_dt = None
        if latest_rental:
            last_rental_dt = _as_utc(latest_rental.end_time) or _as_utc(latest_rental.start_time)
        fallback_dt = _as_utc(battery.updated_at) or _as_utc(battery.created_at)
        ref_dt = last_rental_dt or fallback_dt
        days_idle = 0 if active_tuple else max(0, (now - ref_dt).days) if ref_dt else 0

        status_value = _enum_value(battery.status).lower()
        fault_description = None
        if status_value in {"maintenance", "faulty", "retired", "error"}:
            fault_description = battery.decommission_reason or battery.notes or _enum_value(battery.health_status)

        payload.append(
            {
                "id": battery.id,
                "serial_number": battery.serial_number,
                "station_name": station.name,
                "station_id": station.id,
                "status": status_value,
                "current_charge": float(battery.current_charge or 0.0),
                "health_percentage": float(battery.health_percentage or 0.0),
                "cycle_count": int(battery.cycle_count or 0),
                "battery_type": battery.battery_type or "",
                "current_customer": current_customer,
                "rental_start_time": rental_start_time,
                "last_rental": _iso(last_rental_dt),
                "days_idle": int(days_idle),
                "fault_description": fault_description,
                "last_charged_at": _iso(_as_utc(battery.last_charged_at)),
                "created_at": _iso(_as_utc(battery.created_at)),
            }
        )
    return payload


@router.get("/rentals/active")
def get_dealer_active_rentals(
    station_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    if station_id is not None:
        _assert_station_scope(db, dealer_id, station_id)

    query = (
        select(Rental, User, Battery, Station)
        .join(Station, Rental.start_station_id == Station.id)
        .join(User, User.id == Rental.user_id)
        .outerjoin(Battery, Battery.id == Rental.battery_id)
        .where(
            Station.dealer_id == dealer_id,
            Rental.status.in_(["active", "overdue"]),
        )
    )
    if station_id is not None:
        query = query.where(Station.id == station_id)
    rows = db.exec(query.order_by(Rental.start_time.desc())).all()
    now = datetime.now(UTC)

    payload: list[dict[str, Any]] = []
    for rental, user, battery, station in rows:
        started = _as_utc(rental.start_time)
        duration_minutes = int((now - started).total_seconds() // 60) if started else 0
        payload.append(
            {
                "id": rental.id,
                "customer_name": _user_display_name(user),
                "customer_phone": user.phone_number or "",
                "battery_code": battery.serial_number if battery else "",
                "battery_id": battery.id if battery else 0,
                "station_name": station.name,
                "station_id": station.id,
                "start_time": _iso(started),
                "expected_return": _iso(_as_utc(rental.expected_end_time)),
                "total_amount": float(rental.total_amount or 0.0),
                "late_fee": float(rental.late_fee or 0.0),
                "status": _enum_value(rental.status).lower(),
                "duration_minutes": duration_minutes,
            }
        )
    return payload


@router.get("/reviews")
def get_dealer_reviews(
    station_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    if station_id is not None:
        _assert_station_scope(db, dealer_id, station_id)

    query = (
        select(Review, User, Station)
        .join(Station, Review.station_id == Station.id)
        .join(User, User.id == Review.user_id)
        .where(
            Station.dealer_id == dealer_id,
            Review.is_hidden == False,
        )
    )
    if station_id is not None:
        query = query.where(Station.id == station_id)
    rows = db.exec(query.order_by(Review.created_at.desc())).all()

    payload: list[dict[str, Any]] = []
    for review, user, station in rows:
        payload.append(
            {
                "id": review.id,
                "customer_name": _user_display_name(user),
                "rating": int(review.rating or 0),
                "comment": review.comment,
                "station_name": station.name,
                "station_id": station.id,
                "created_at": _iso(_as_utc(review.created_at)),
                "response_from_station": review.response_from_station,
                "replied_at": _iso(_as_utc(review.created_at)) if review.response_from_station else None,
                "is_verified_rental": bool(review.is_verified_rental),
            }
        )
    return payload


@router.post("/reviews/{review_id}/reply")
def reply_to_review(
    review_id: int,
    payload: ReviewReplyReq,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    reply_text = payload.reply_text.strip()
    if not reply_text:
        raise HTTPException(status_code=400, detail="Reply text cannot be empty")

    row = db.exec(
        select(Review, Station)
        .join(Station, Review.station_id == Station.id)
        .where(
            Review.id == review_id,
            Station.dealer_id == dealer_id,
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    review, station = row

    review.response_from_station = reply_text
    db.add(review)
    db.commit()
    db.refresh(review)

    return {
        "message": "Reply saved",
        "review": {
            "id": review.id,
            "station_id": station.id,
            "response_from_station": review.response_from_station,
            "replied_at": _iso(datetime.now(UTC)),
        },
    }


@router.get("/swaps/list")
def get_dealer_swaps(
    station_id: int | None = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    if station_id is not None:
        _assert_station_scope(db, dealer_id, station_id)

    old_battery = aliased(Battery)
    new_battery = aliased(Battery)
    query = (
        select(SwapSession, User, Station, old_battery, new_battery)
        .join(Station, SwapSession.station_id == Station.id)
        .join(User, User.id == SwapSession.user_id)
        .outerjoin(old_battery, old_battery.id == SwapSession.old_battery_id)
        .outerjoin(new_battery, new_battery.id == SwapSession.new_battery_id)
        .where(Station.dealer_id == dealer_id)
    )
    if station_id is not None:
        query = query.where(Station.id == station_id)
    rows = db.exec(query.order_by(SwapSession.created_at.desc())).all()

    payload: list[dict[str, Any]] = []
    for swap, user, station, old_batt, new_batt in rows:
        payload.append(
            {
                "id": swap.id,
                "customer_name": _user_display_name(user),
                "customer_id": user.id if user else 0,
                "station_name": station.name,
                "station_id": station.id,
                "old_battery_code": old_batt.serial_number if old_batt else "",
                "new_battery_code": new_batt.serial_number if new_batt else "",
                "old_battery_soc": float(swap.old_battery_soc or 0.0),
                "new_battery_soc": float(swap.new_battery_soc or 0.0),
                "swap_amount": float(swap.swap_amount or 0.0),
                "status": _enum_value(swap.status).lower(),
                "payment_status": _enum_value(swap.payment_status).lower(),
                "created_at": _iso(_as_utc(swap.created_at)),
                "completed_at": _iso(_as_utc(swap.completed_at)),
            }
        )
    return payload


@router.get("/{station_id}/activity")
def get_station_activity(
    station_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    _assert_station_scope(db, dealer_id, station_id)

    swap_rows = db.exec(
        select(SwapSession, User, Battery)
        .join(User, User.id == SwapSession.user_id)
        .outerjoin(Battery, Battery.id == SwapSession.old_battery_id)
        .where(SwapSession.station_id == station_id)
        .order_by(SwapSession.created_at.desc())
        .limit(limit)
    ).all()
    rental_rows = db.exec(
        select(Rental, User, Battery)
        .join(User, User.id == Rental.user_id)
        .outerjoin(Battery, Battery.id == Rental.battery_id)
        .where(Rental.start_station_id == station_id)
        .order_by(Rental.start_time.desc())
        .limit(limit)
    ).all()

    combined: list[dict[str, Any]] = []
    for swap, user, battery in swap_rows:
        status = _enum_value(swap.status).lower()
        customer = _user_display_name(user)
        if status in {"completed", "success"}:
            event_type = "completed"
            description = f"Swap completed for {customer}"
        elif status in {"failed", "error"}:
            event_type = "fault"
            description = f"Swap failed for {customer}"
        else:
            event_type = "start"
            description = f"Swap in progress for {customer}"
        combined.append(
            {
                "_ts": _as_utc(swap.created_at),
                "event_type": event_type,
                "description": description,
                "battery_code": battery.serial_number if battery else None,
                "customer_name": customer,
                "amount": float(swap.swap_amount or 0.0),
            }
        )

    for rental, user, battery in rental_rows:
        status = _enum_value(rental.status).lower()
        customer = _user_display_name(user)
        if status in {"active", "overdue"}:
            event_type = "rental"
            description = f"{customer} started a rental"
        elif status == "completed":
            event_type = "return"
            description = f"{customer} completed a rental"
        else:
            event_type = "warning"
            description = f"Rental status updated for {customer}"
        combined.append(
            {
                "_ts": _as_utc(rental.start_time) or _as_utc(rental.created_at),
                "event_type": event_type,
                "description": description,
                "battery_code": battery.serial_number if battery else None,
                "customer_name": customer,
                "amount": float(rental.total_amount or 0.0),
            }
        )

    combined = [item for item in combined if item["_ts"] is not None]
    combined.sort(key=lambda item: item["_ts"], reverse=True)
    payload: list[dict[str, Any]] = []
    for idx, event in enumerate(combined[:limit], start=1):
        payload.append(
            {
                "id": idx,
                "event_type": event["event_type"],
                "description": event["description"],
                "created_at": _iso(event["_ts"]),
                "battery_code": event["battery_code"],
                "customer_name": event["customer_name"],
                "amount": event["amount"],
            }
        )
    return payload


@router.get("/{station_id}/transactions")
def get_station_transactions(
    station_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    dealer_id = _get_dealer_id(db, current_user.id)
    _assert_station_scope(db, dealer_id, station_id)

    rows = db.exec(
        select(Transaction, Rental, User)
        .join(Rental, Transaction.rental_id == Rental.id)
        .join(User, User.id == Transaction.user_id)
        .where(
            Rental.start_station_id == station_id,
            or_(
                Transaction.status == "SUCCESS",
                Transaction.status == "success",
                Transaction.status.is_(None),
            ),
        )
        .order_by(Transaction.created_at.desc())
        .limit(limit)
    ).all()

    payload: list[dict[str, Any]] = []
    for tx, rental, user in rows:
        raw_type = _enum_value(tx.transaction_type) or tx.type or tx.category or "Transaction"
        payload.append(
            {
                "id": tx.id,
                "type": raw_type.replace("_", " ").title(),
                "customer": _user_display_name(user),
                "amount": float(tx.amount or 0.0),
                "time": _iso(_as_utc(tx.created_at)),
            }
        )
    return payload
