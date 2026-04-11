"""
Dealer Station API — Endpoints for dealers to manage their stations, monitor
inventory, update rules, and schedule maintenance.
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, select, func
from datetime import datetime, UTC
import csv
import io

from app.db.session import get_session
from app.api.deps import get_current_user
from app.core.config import settings
from jose import jwt
from app.schemas.user import TokenPayload
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.station import Station, StationSlot
from app.models.rental import Rental
from app.models.maintenance import MaintenanceRecord
from app.models.battery import Battery, BatteryStatus
from app.models.swap import SwapSession
from app.models.review import Review
from app.services.dealer_station_service import DealerStationService
from pydantic import BaseModel
from app.utils.audit_context import log_audit_action
from app.models.audit_log import AuditActionType

router = APIRouter()


# ─── NEW: Dealer Quick Stats ───
@router.get("/stats")
def get_dealer_stats(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Aggregated stats across all dealer's stations."""
    dealer_id = _get_dealer_id(db, current_user.id)
    stations = db.exec(select(Station).where(Station.dealer_id == dealer_id)).all()
    station_ids = [s.id for s in stations]

    if not station_ids:
        return {"available_batteries": 0, "total_batteries": 0, "ongoing_rentals": 0, "current_swaps": 0, "avg_rating": 0.0, "station_count": 0}

    # Dynamically compute battery counts from core.batteries
    total_batteries = db.exec(
        select(func.count(Battery.id)).where(Battery.station_id.in_(station_ids))
    ).one() or 0

    available = db.exec(
        select(func.count(Battery.id)).where(
            Battery.station_id.in_(station_ids),
            Battery.status == BatteryStatus.AVAILABLE,
        )
    ).one() or 0

    ongoing_rentals = 0
    try:
        ongoing_rentals = db.exec(
            select(func.count(Rental.id)).where(
                Rental.start_station_id.in_(station_ids),
                Rental.status == "active",
            )
        ).one() or 0
    except Exception:
        pass

    current_swaps = 0
    try:
        current_swaps = db.exec(
            select(func.count(SwapSession.id)).where(
                SwapSession.station_id.in_(station_ids),
                SwapSession.status.in_(["initiated", "processing"]),
            )
        ).one() or 0
    except Exception:
        pass

    avg_rating = 0.0
    rated_stations = [s for s in stations if s.rating > 0]
    if rated_stations:
        avg_rating = round(sum(s.rating for s in rated_stations) / len(rated_stations), 1)

    return {
        "available_batteries": available,
        "total_batteries": total_batteries,
        "ongoing_rentals": ongoing_rentals,
        "current_swaps": current_swaps,
        "avg_rating": avg_rating,
        "station_count": len(stations),
    }


# ─── NEW: Dealer Batteries List ───
@router.get("/batteries")
def get_dealer_batteries(
    station_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(200, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List batteries across dealer's stations with optional filters."""
    dealer_id = _get_dealer_id(db, current_user.id)
    stations = db.exec(select(Station).where(Station.dealer_id == dealer_id)).all()
    station_ids = [s.id for s in stations]
    station_map = {s.id: s.name for s in stations}

    if not station_ids:
        return []

    query = select(Battery).where(Battery.station_id.in_(station_ids))
    if station_id:
        query = query.where(Battery.station_id == station_id)
    if status:
        query = query.where(Battery.status == status)

    batteries = db.exec(query.order_by(Battery.created_at.desc()).limit(limit).offset(offset)).all()

    if not batteries:
        return []

    # Batch fetch active rentals for ALL batteries in one query (eliminates N+1)
    battery_ids = [b.id for b in batteries]
    active_rental_map = {}
    try:
        active_rentals = db.exec(
            select(Rental).where(
                Rental.battery_id.in_(battery_ids),
                Rental.status == "active",
            )
        ).all()
        active_rental_map = {r.battery_id: r for r in active_rentals}
    except Exception:
        pass

    result = []
    for b in batteries:
        active_rental = active_rental_map.get(b.id)
        fault_desc = None
        try:
            if b.health_status and str(b.health_status) in ("DAMAGED", "POOR", "CRITICAL"):
                fault_desc = b.notes
        except Exception:
            pass

        result.append({
            "id": b.id,
            "serial_number": b.serial_number,
            "station_id": b.station_id,
            "station_name": station_map.get(b.station_id, ""),
            "status": b.status.value if hasattr(b.status, 'value') else str(b.status),
            "current_charge": round(b.current_charge, 1) if b.current_charge else 0.0,
            "health_percentage": round(b.health_percentage, 1) if b.health_percentage else 100.0,
            "cycle_count": b.cycle_count or 0,
            "battery_type": b.battery_type or "",
            "current_customer": None,
            "rental_start_time": str(active_rental.start_time) if active_rental and hasattr(active_rental, 'start_time') else None,
            "days_idle": 0,
            "fault_description": fault_desc,
            "last_charged_at": str(b.last_charged_at) if b.last_charged_at else None,
            "created_at": str(b.created_at) if b.created_at else None,
        })

    return result


# ─── NEW: Active Rentals ───
@router.get("/rentals/active")
def get_active_rentals(
    station_id: int | None = Query(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List active rentals across dealer's stations."""
    dealer_id = _get_dealer_id(db, current_user.id)
    stations = db.exec(select(Station).where(Station.dealer_id == dealer_id)).all()
    station_ids = [s.id for s in stations]
    station_map = {s.id: s.name for s in stations}

    if not station_ids:
        return []

    query = select(Rental).where(
        Rental.start_station_id.in_(station_ids),
        Rental.status.in_(["active", "overdue"]),
    )
    if station_id:
        query = query.where(Rental.start_station_id == station_id)

    rentals = db.exec(query.order_by(Rental.start_time.desc())).all()

    # Batch fetch all customers and batteries to avoid N+1
    user_ids = list(set(r.user_id for r in rentals))
    battery_ids = list(set(r.battery_id for r in rentals))
    customers_map = {}
    batteries_map = {}
    if user_ids:
        users = db.exec(select(User).where(User.id.in_(user_ids))).all()
        customers_map = {u.id: u for u in users}
    if battery_ids:
        batts = db.exec(select(Battery).where(Battery.id.in_(battery_ids))).all()
        batteries_map = {b.id: b for b in batts}

    result = []
    for r in rentals:
        customer = customers_map.get(r.user_id)
        customer_name = customer.full_name if customer and customer.full_name else f"User #{r.user_id}"
        customer_phone = customer.phone_number if customer and customer.phone_number else ""

        battery = batteries_map.get(r.battery_id)
        battery_code = battery.serial_number if battery else f"BAT-{r.battery_id}"

        result.append({
            "id": r.id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "battery_code": battery_code,
            "battery_id": r.battery_id,
            "station_name": station_map.get(r.start_station_id, ""),
            "station_id": r.start_station_id,
            "start_time": str(r.start_time),
            "expected_return": str(r.expected_end_time),
            "total_amount": r.total_amount,
            "late_fee": r.late_fee,
            "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
            "duration_minutes": int((r.expected_end_time - r.start_time).total_seconds() / 60) if r.expected_end_time else 0,
        })

    return result


# ─── NEW: Reviews ───
@router.get("/reviews")
def get_dealer_reviews(
    station_id: int | None = Query(None),
    rating: int | None = Query(None),
    replied: bool | None = Query(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List reviews for dealer's stations."""
    dealer_id = _get_dealer_id(db, current_user.id)
    stations = db.exec(select(Station).where(Station.dealer_id == dealer_id)).all()
    station_ids = [s.id for s in stations]
    station_map = {s.id: s.name for s in stations}

    if not station_ids:
        return []

    query = select(Review).where(Review.station_id.in_(station_ids))
    if station_id:
        query = query.where(Review.station_id == station_id)
    if rating:
        query = query.where(Review.rating == rating)
    if replied is True:
        query = query.where(Review.response_from_station.isnot(None))
    elif replied is False:
        query = query.where(Review.response_from_station.is_(None))

    reviews = db.exec(query.order_by(Review.created_at.desc())).all()

    result = []
    for rv in reviews:
        customer = db.get(User, rv.user_id)
        customer_name = customer.full_name if customer and hasattr(customer, 'full_name') else f"User #{rv.user_id}"

        result.append({
            "id": rv.id,
            "customer_name": customer_name,
            "rating": rv.rating,
            "comment": rv.comment,
            "station_id": rv.station_id,
            "station_name": station_map.get(rv.station_id, ""),
            "response_from_station": rv.response_from_station,
            "replied_at": None,
            "is_verified_rental": rv.is_verified_rental,
            "created_at": str(rv.created_at),
        })

    return result


class ReplyRequest(BaseModel):
    reply_text: str


# ─── NEW: Reply to Review ───
@router.post("/reviews/{review_id}/reply")
def reply_to_review(
    review_id: int,
    data: ReplyRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Dealer replies to a customer review."""
    dealer_id = _get_dealer_id(db, current_user.id)
    stations = db.exec(select(Station).where(Station.dealer_id == dealer_id)).all()
    station_ids = [s.id for s in stations]

    review = db.get(Review, review_id)
    if not review or review.station_id not in station_ids:
        raise HTTPException(status_code=404, detail="Review not found")

    review.response_from_station = data.reply_text
    db.add(review)
    db.commit()
    return {"message": "Reply saved", "review_id": review_id}


class StatusChangeRequest(BaseModel):
    status: str
    reason: str | None = None


# ─── NEW: Change Station Status ───
@router.put("/{station_id}/status")
def change_station_status(
    station_id: int,
    data: StatusChangeRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Change station operational status."""
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(
        select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)
    ).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    valid_statuses = ["OPERATIONAL", "OFFLINE", "MAINTENANCE", "CLOSED"]
    if data.status.upper() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    station.status = data.status.upper()
    station.updated_at = datetime.now(UTC)
    db.add(station)
    db.commit()
    return {"message": f"Station status changed to {data.status.upper()}", "id": station_id}

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
        # Dynamically compute battery counts from core.batteries
        total_batteries = db.exec(
            select(func.count(Battery.id)).where(Battery.station_id == s.id)
        ).one() or 0

        available_count = db.exec(
            select(func.count(Battery.id)).where(
                Battery.station_id == s.id,
                Battery.status == BatteryStatus.AVAILABLE,
            )
        ).one() or 0

        rented_count = db.exec(
            select(func.count(Battery.id)).where(
                Battery.station_id == s.id,
                Battery.status == BatteryStatus.RENTED,
            )
        ).one() or 0

        maintenance_count = db.exec(
            select(func.count(Battery.id)).where(
                Battery.station_id == s.id,
                Battery.status == BatteryStatus.MAINTENANCE,
            )
        ).one() or 0

        damaged_count = db.exec(
            select(func.count(Battery.id)).where(
                Battery.station_id == s.id,
                Battery.status.in_([BatteryStatus.RETIRED]),
            )
        ).one() or 0

        charging_count = db.exec(
            select(func.count(Battery.id)).where(
                Battery.station_id == s.id,
                Battery.status == BatteryStatus.CHARGING,
            )
        ).one() or 0

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
        utilization = round((total_batteries / total_slots) * 100, 1) if total_slots > 0 else 0

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
            "total_batteries": total_batteries,
            "available_batteries": available_count,
            "rented_batteries": rented_count,
            "charging_batteries": charging_count,
            "maintenance_batteries": maintenance_count,
            "damaged_batteries": damaged_count,
            "available_slots": max(0, (s.total_slots or 0) - total_batteries),
            "is_24x7": s.is_24x7,
            "rating": round(s.rating, 1),
            "active_swaps": active_rentals,
            "ongoing_rentals": rented_count,
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

    # ── Dynamic battery counts from batteries table ──
    total_batteries = db.exec(
        select(func.count(Battery.id)).where(Battery.station_id == station_id)
    ).one() or 0

    available_count = db.exec(
        select(func.count(Battery.id)).where(
            Battery.station_id == station_id,
            Battery.status == BatteryStatus.AVAILABLE,
        )
    ).one() or 0

    rented_count = db.exec(
        select(func.count(Battery.id)).where(
            Battery.station_id == station_id,
            Battery.status == BatteryStatus.RENTED,
        )
    ).one() or 0

    charging_count = db.exec(
        select(func.count(Battery.id)).where(
            Battery.station_id == station_id,
            Battery.status == BatteryStatus.CHARGING,
        )
    ).one() or 0

    maintenance_count = db.exec(
        select(func.count(Battery.id)).where(
            Battery.station_id == station_id,
            Battery.status == BatteryStatus.MAINTENANCE,
        )
    ).one() or 0

    damaged_count = db.exec(
        select(func.count(Battery.id)).where(
            Battery.station_id == station_id,
            Battery.status == BatteryStatus.RETIRED,
        )
    ).one() or 0

    # ── Active rentals count ──
    active_rentals = db.exec(
        select(func.count(Rental.id)).where(
            Rental.start_station_id == station_id,
            Rental.status == "active",
        )
    ).one() or 0

    # ── Today's revenue ──
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    today_rental_revenue = db.exec(
        select(func.coalesce(func.sum(Rental.total_amount), 0)).where(
            Rental.start_station_id == station_id,
            Rental.start_time >= today_start,
        )
    ).one() or 0
    today_swap_revenue = 0
    try:
        today_swap_revenue = db.exec(
            select(func.coalesce(func.sum(SwapSession.swap_amount), 0)).where(
                SwapSession.station_id == station_id,
                SwapSession.created_at >= today_start,
                SwapSession.status == "completed",
            )
        ).one() or 0
    except Exception:
        pass
    today_revenue = round(float(today_rental_revenue) + float(today_swap_revenue), 2)

    # ── Slots ──
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

    # ── Recent rentals ──
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

    # ── Maintenance history ──
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

    # ── Slot utilization ──
    total_slots = station.total_slots or 1
    utilization = round((total_batteries / total_slots) * 100, 1) if total_slots > 0 else 0

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
            "total_batteries": total_batteries,
            "available_batteries": available_count,
            "rented_batteries": rented_count,
            "charging_batteries": charging_count,
            "maintenance_batteries": maintenance_count,
            "damaged_batteries": damaged_count,
            "available_slots": max(0, (station.total_slots or 0) - total_batteries),
            "is_24x7": station.is_24x7,
            "rating": round(station.rating, 1),
            "ongoing_rentals": active_rentals,
            "today_revenue": today_revenue,
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


# ─── NEW: Station Activity Feed ───
@router.get("/{station_id}/activity")
def get_station_activity(
    station_id: int,
    limit: int = Query(20, le=50),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get recent activity events for a specific station from real DB data."""
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(
        select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)
    ).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    events = []

    # Recent rentals (started)
    recent_rentals = db.exec(
        select(Rental)
        .where(Rental.start_station_id == station_id)
        .order_by(Rental.start_time.desc())
        .limit(limit)
    ).all()

    user_ids = list(set(r.user_id for r in recent_rentals))
    users_map = {}
    if user_ids:
        users = db.exec(select(User).where(User.id.in_(user_ids))).all()
        users_map = {u.id: u for u in users}

    bat_ids = list(set(r.battery_id for r in recent_rentals))
    bats_map = {}
    if bat_ids:
        batts = db.exec(select(Battery).where(Battery.id.in_(bat_ids))).all()
        bats_map = {b.id: b for b in batts}

    for r in recent_rentals:
        customer = users_map.get(r.user_id)
        customer_name = customer.full_name if customer and customer.full_name else f"User #{r.user_id}"
        battery = bats_map.get(r.battery_id)
        bat_code = battery.serial_number if battery else f"BAT-{r.battery_id}"

        if r.status.value if hasattr(r.status, 'value') else str(r.status) == "active":
            events.append({
                "id": r.id,
                "event_type": "rental",
                "description": f"New rental started — {customer_name} ({bat_code})",
                "created_at": str(r.start_time),
                "battery_code": bat_code,
                "customer_name": customer_name,
                "amount": r.total_amount,
            })
        elif r.status.value if hasattr(r.status, 'value') else str(r.status) == "completed":
            events.append({
                "id": r.id,
                "event_type": "return",
                "description": f"Battery {bat_code} returned by {customer_name}",
                "created_at": str(r.end_time or r.start_time),
                "battery_code": bat_code,
                "customer_name": customer_name,
                "amount": r.total_amount,
            })

    # Recent swaps
    try:
        recent_swaps = db.exec(
            select(SwapSession)
            .where(SwapSession.station_id == station_id)
            .order_by(SwapSession.created_at.desc())
            .limit(limit)
        ).all()

        swap_user_ids = list(set(s.user_id for s in recent_swaps))
        if swap_user_ids:
            swap_users = db.exec(select(User).where(User.id.in_(swap_user_ids))).all()
            swap_users_map = {u.id: u for u in swap_users}
        else:
            swap_users_map = {}

        for s in recent_swaps:
            customer = swap_users_map.get(s.user_id)
            customer_name = customer.full_name if customer and customer.full_name else f"User #{s.user_id}"
            old_bat = db.get(Battery, s.old_battery_id) if s.old_battery_id else None
            bat_code = old_bat.serial_number if old_bat else ""

            events.append({
                "id": s.id + 100000,  # offset to avoid ID collision with rentals
                "event_type": "completed" if s.status == "completed" else "swap",
                "description": f"Battery {bat_code} swap {'completed' if s.status == 'completed' else 'initiated'} by {customer_name}",
                "created_at": str(s.completed_at or s.created_at),
                "battery_code": bat_code,
                "customer_name": customer_name,
                "amount": s.swap_amount,
            })
    except Exception:
        pass

    # Sort all events by timestamp desc
    events.sort(key=lambda e: e["created_at"], reverse=True)
    return events[:limit]


# ─── NEW: Station Transactions ───
@router.get("/{station_id}/transactions")
def get_station_transactions(
    station_id: int,
    limit: int = Query(10, le=50),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get recent financial transactions for a station."""
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(
        select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)
    ).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    transactions = []

    # Rental payments
    rentals = db.exec(
        select(Rental)
        .where(Rental.start_station_id == station_id, Rental.total_amount > 0)
        .order_by(Rental.start_time.desc())
        .limit(limit)
    ).all()

    user_ids = list(set(r.user_id for r in rentals))
    users_map = {}
    if user_ids:
        users = db.exec(select(User).where(User.id.in_(user_ids))).all()
        users_map = {u.id: u for u in users}

    for r in rentals:
        customer = users_map.get(r.user_id)
        customer_name = customer.full_name if customer and customer.full_name else f"User #{r.user_id}"
        transactions.append({
            "id": r.id,
            "type": "Rental",
            "customer": customer_name,
            "amount": r.total_amount,
            "time": str(r.start_time),
        })
        # Add late fee as separate transaction if applicable
        if r.late_fee and r.late_fee > 0:
            transactions.append({
                "id": r.id + 500000,
                "type": "Late Fee",
                "customer": customer_name,
                "amount": r.late_fee,
                "time": str(r.end_time or r.start_time),
            })

    # Swap fees
    try:
        swaps = db.exec(
            select(SwapSession)
            .where(SwapSession.station_id == station_id, SwapSession.swap_amount > 0)
            .order_by(SwapSession.created_at.desc())
            .limit(limit)
        ).all()

        swap_user_ids = list(set(s.user_id for s in swaps))
        if swap_user_ids:
            swap_users = db.exec(select(User).where(User.id.in_(swap_user_ids))).all()
            swap_users_map = {u.id: u for u in swap_users}
        else:
            swap_users_map = {}

        for s in swaps:
            customer = swap_users_map.get(s.user_id)
            customer_name = customer.full_name if customer and customer.full_name else f"User #{s.user_id}"
            transactions.append({
                "id": s.id + 200000,
                "type": "Swap Fee",
                "customer": customer_name,
                "amount": s.swap_amount,
                "time": str(s.completed_at or s.created_at),
            })
    except Exception:
        pass

    # Sort by time desc
    transactions.sort(key=lambda t: t["time"], reverse=True)
    return transactions[:limit]


# ─── NEW: Dealer Swaps ───
@router.get("/swaps/list")
def get_dealer_swaps(
    station_id: int | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List swap sessions across dealer's stations."""
    dealer_id = _get_dealer_id(db, current_user.id)
    stations = db.exec(select(Station).where(Station.dealer_id == dealer_id)).all()
    station_ids = [s.id for s in stations]
    station_map = {s.id: s.name for s in stations}

    if not station_ids:
        return []

    query = select(SwapSession).where(SwapSession.station_id.in_(station_ids))
    if station_id:
        query = query.where(SwapSession.station_id == station_id)
    if status:
        query = query.where(SwapSession.status == status)

    swaps = db.exec(query.order_by(SwapSession.created_at.desc()).limit(limit)).all()

    # Batch fetch users and batteries
    user_ids = list(set(s.user_id for s in swaps))
    users_map = {}
    if user_ids:
        users = db.exec(select(User).where(User.id.in_(user_ids))).all()
        users_map = {u.id: u for u in users}

    bat_ids = set()
    for s in swaps:
        if s.old_battery_id: bat_ids.add(s.old_battery_id)
        if s.new_battery_id: bat_ids.add(s.new_battery_id)
    bats_map = {}
    if bat_ids:
        batts = db.exec(select(Battery).where(Battery.id.in_(list(bat_ids)))).all()
        bats_map = {b.id: b for b in batts}

    result = []
    for s in swaps:
        customer = users_map.get(s.user_id)
        customer_name = customer.full_name if customer and customer.full_name else f"User #{s.user_id}"
        old_bat = bats_map.get(s.old_battery_id) if s.old_battery_id else None
        new_bat = bats_map.get(s.new_battery_id) if s.new_battery_id else None

        result.append({
            "id": s.id,
            "customer_name": customer_name,
            "customer_id": s.user_id,
            "station_name": station_map.get(s.station_id, ""),
            "station_id": s.station_id,
            "old_battery_code": old_bat.serial_number if old_bat else "",
            "new_battery_code": new_bat.serial_number if new_bat else "",
            "old_battery_soc": s.old_battery_soc,
            "new_battery_soc": s.new_battery_soc,
            "swap_amount": s.swap_amount,
            "status": s.status,
            "payment_status": s.payment_status,
            "created_at": str(s.created_at),
            "completed_at": str(s.completed_at) if s.completed_at else None,
        })

    return result


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


@router.patch("/{station_id}/settings")
def update_station_settings(
    station_id: int,
    data: StationUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update primary details of a station."""
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(
        select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)
    ).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    update_data = data.dict(exclude_unset=True)
    if not update_data:
        return station

    for key, val in update_data.items():
        setattr(station, key, val)
        
    station.updated_at = datetime.now(UTC)
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


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

def get_user_from_qs(token: str = Query(...), db: Session = Depends(get_session)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_data = TokenPayload(**payload)
        user = db.exec(select(User).where(User.id == int(token_data.sub))).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/{station_id}/export/swaps")
def export_swaps_csv(
    station_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_user_from_qs),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    swaps = db.exec(select(SwapSession).where(SwapSession.station_id == station_id).order_by(SwapSession.created_at.desc())).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Swap ID", "Customer ID", "Old Battery ID", "Old SOC (%)", "New Battery ID", "New SOC (%)", "Amount", "Status", "Date"])
    
    for s in swaps:
        writer.writerow([
            s.id, s.user_id, s.old_battery_id or "", s.old_battery_soc or "", 
            s.new_battery_id or "", s.new_battery_soc or "", s.swap_amount, s.status, s.created_at
        ])
    
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=station_{station_id}_swaps.csv"})


@router.get("/{station_id}/export/rentals")
def export_rentals_csv(
    station_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_user_from_qs),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    rentals = db.exec(select(Rental).where(Rental.start_station_id == station_id).order_by(Rental.start_time.desc())).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Rental ID", "Customer ID", "Battery ID", "Status", "Total Amount", "Start Time", "End Time"])
    
    for r in rentals:
        writer.writerow([
            r.id, r.user_id, r.battery_id, r.status, r.total_amount, r.start_time, r.end_time or ""
        ])
    
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=station_{station_id}_rentals.csv"})


@router.get("/{station_id}/export/reviews")
def export_reviews_csv(
    station_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_user_from_qs),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    reviews = db.exec(select(Review).where(Review.station_id == station_id).order_by(Review.created_at.desc())).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Review ID", "Customer ID", "Rating", "Comment", "Replied", "Date"])
    
    for r in reviews:
        writer.writerow([
            r.id, r.user_id, r.rating, r.comment or "", 
            "Yes" if r.dealer_reply else "No", r.created_at
        ])
    
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=station_{station_id}_reviews.csv"})


@router.get("/{station_id}/export/batteries")
def export_batteries_csv(
    station_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_user_from_qs),
):
    dealer_id = _get_dealer_id(db, current_user.id)
    station = db.exec(select(Station).where(Station.id == station_id, Station.dealer_id == dealer_id)).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    batteries = db.exec(select(Battery).where(Battery.current_station_id == station_id).order_by(Battery.battery_code)).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Battery ID", "Battery Code", "Status", "SOC (%)", "Health Status", "Cycles", "Last Seen"])
    
    for b in batteries:
        writer.writerow([
            b.id, b.battery_code, b.status, b.soc, b.health_status, b.cycles, b.last_seen_at
        ])
    
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=station_{station_id}_batteries.csv"})

