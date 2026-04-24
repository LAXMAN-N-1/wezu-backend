from __future__ import annotations
"""
Customer Reservations API
Matches the Flutter ReservationRepositoryImpl expected paths:
  POST /stations/{station_id}/reserve
  GET  /reservations/active
  PUT  /reservations/{reservation_id}/cancel
  GET  /reservations/{reservation_id}/status
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime, timedelta, timezone; UTC = timezone.utc
from typing import Optional
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.models.battery_reservation import BatteryReservation
from app.models.station import Station

router = APIRouter()


class ReserveRequest(BaseModel):
    battery_type: Optional[str] = None
    duration_minutes: int = 15


class ReservationResponse(BaseModel):
    id: int
    station_id: int
    station_name: str
    station_address: str
    battery_type: str
    start_time: datetime
    expiry_time: datetime
    status: str
    latitude: float
    longitude: float
    fee: float


@router.post("/stations/{station_id}/reserve", response_model=ReservationResponse)
async def reserve_battery(
    station_id: int,
    reserve_in: ReserveRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Reserve a battery slot at a station for up to 15 minutes."""
    # Check for existing active reservation
    existing = db.exec(
        select(BatteryReservation).where(
            BatteryReservation.user_id == current_user.id,
            BatteryReservation.status == "ACTIVE",
        )
    ).first()

    if existing:
        # Check if expired
        if existing.end_time < datetime.now(UTC):
            existing.status = "EXPIRED"
            db.add(existing)
            db.commit()
        else:
            raise HTTPException(
                status_code=400, detail="You already have an active reservation"
            )

    # Verify station exists
    station = db.get(Station, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    now = datetime.now(UTC)
    reservation = BatteryReservation(
        user_id=current_user.id,
        station_id=station_id,
        start_time=now,
        end_time=now + timedelta(minutes=reserve_in.duration_minutes),
        status="ACTIVE",
    )

    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    return ReservationResponse(
        id=reservation.id,
        station_id=station.id,
        station_name=station.name,
        station_address=station.address,
        battery_type=reserve_in.battery_type or "48V/30Ah",
        start_time=reservation.start_time,
        expiry_time=reservation.end_time,
        status=reservation.status.lower(),
        latitude=station.latitude,
        longitude=station.longitude,
        fee=0.0,  # Free for MVP
    )


@router.get("/reservations/active", response_model=Optional[ReservationResponse])
async def get_active_reservation(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get the user's current active reservation, if any."""
    reservation = db.exec(
        select(BatteryReservation).where(
            BatteryReservation.user_id == current_user.id,
            BatteryReservation.status == "ACTIVE",
        )
    ).first()

    if not reservation:
        return None

    # Auto-expire check
    if reservation.end_time < datetime.now(UTC):
        reservation.status = "EXPIRED"
        db.add(reservation)
        db.commit()
        return None

    station = db.get(Station, reservation.station_id)
    if not station:
        return None

    return ReservationResponse(
        id=reservation.id,
        station_id=station.id,
        station_name=station.name,
        station_address=station.address,
        battery_type="48V/30Ah",
        start_time=reservation.start_time,
        expiry_time=reservation.end_time,
        status=reservation.status.lower(),
        latitude=station.latitude,
        longitude=station.longitude,
        fee=0.0,
    )


@router.put("/reservations/{reservation_id}/cancel")
async def cancel_reservation(
    reservation_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Cancel a reservation."""
    reservation = db.get(BatteryReservation, reservation_id)
    if not reservation or reservation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Reservation not found")

    reservation.status = "CANCELLED"
    db.add(reservation)
    db.commit()
    return {"message": "Reservation cancelled", "status": "cancelled"}


@router.get("/reservations/{reservation_id}/status")
async def get_reservation_status(
    reservation_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get reservation status."""
    reservation = db.get(BatteryReservation, reservation_id)
    if not reservation or reservation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Reservation not found")

    # Auto-expire check
    if reservation.status == "ACTIVE" and reservation.end_time < datetime.now(UTC):
        reservation.status = "EXPIRED"
        db.add(reservation)
        db.commit()

    return {"status": reservation.status.lower()}
