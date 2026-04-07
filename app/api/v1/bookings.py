from __future__ import annotations

from datetime import UTC, datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api import deps
from app.core.config import settings
from app.models.battery_reservation import BatteryReservation
from app.models.financial import Transaction, TransactionStatus, TransactionType, Wallet
from app.models.station import Station
from app.models.user import User
from app.schemas.booking import (
    BookingCreate,
    BookingPaymentRequest,
    BookingPaymentResponse,
    BookingResponse,
    BookingUpdate,
)
from app.services.booking_service import BookingService
from app.services.notification_service import NotificationService

router = APIRouter()


def _get_user_booking_or_404(db: Session, booking_id: int, user_id: int) -> BatteryReservation:
    booking = db.get(BatteryReservation, booking_id)
    if not booking or booking.user_id != user_id:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/", response_model=BookingResponse)
async def create_booking(
    booking_in: BookingCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Create a new battery reservation with lifecycle validation."""
    try:
        return BookingService.create_reservation(db, current_user.id, booking_in.station_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/", response_model=List[BookingResponse])
async def list_my_bookings(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """List current user's reservations, expiring stale pending records first."""
    BookingService.release_expired_reservations(db, user_id=current_user.id)
    statement = (
        select(BatteryReservation)
        .where(BatteryReservation.user_id == current_user.id)
        .order_by(BatteryReservation.created_at.desc())
    )
    return db.exec(statement).all()


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_details(
    booking_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get reservation details and update status if reservation has expired."""
    booking = _get_user_booking_or_404(db, booking_id, current_user.id)
    BookingService.mark_expired_if_due(db, booking)
    return booking


@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: int,
    booking_in: BookingUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Update reservation status with allowed state transitions only."""
    booking = _get_user_booking_or_404(db, booking_id, current_user.id)
    BookingService.mark_expired_if_due(db, booking)

    if not booking_in.status:
        return booking

    target_status = booking_in.status.strip().upper()
    current_status = (booking.status or "").strip().upper()

    if target_status == current_status:
        return booking

    if not BookingService.is_transition_allowed(current_status, target_status):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition booking from {current_status} to {target_status}",
        )

    booking.status = target_status
    booking.updated_at = datetime.utcnow()

    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@router.delete("/{booking_id}")
async def cancel_booking(
    booking_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Cancel a pending/active reservation."""
    booking = _get_user_booking_or_404(db, booking_id, current_user.id)
    BookingService.mark_expired_if_due(db, booking)

    current_status = (booking.status or "").strip().upper()
    if current_status in {"COMPLETED", "EXPIRED"}:
        raise HTTPException(status_code=400, detail=f"Cannot cancel booking in {current_status} state")
    if current_status == "CANCELLED":
        return {"message": "Booking already cancelled", "booking_id": booking.id}

    if not BookingService.is_transition_allowed(current_status, "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel booking in {current_status} state")

    booking.status = "CANCELLED"
    booking.updated_at = datetime.utcnow()
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return {"message": "Booking cancelled", "booking_id": booking.id}


@router.post("/{booking_id}/reminder")
async def send_booking_reminder(
    booking_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Send reminder notification for booking if still valid."""
    booking = _get_user_booking_or_404(db, booking_id, current_user.id)
    BookingService.mark_expired_if_due(db, booking)

    if (booking.status or "").strip().upper() == "EXPIRED":
        raise HTTPException(status_code=400, detail="Cannot send reminder for expired booking")

    station = db.get(Station, booking.station_id)
    station_name = station.name if station else f"Station #{booking.station_id}"
    booking_end_time = booking.end_time
    if booking_end_time.tzinfo is None:
        booking_end_iso = booking_end_time.replace(tzinfo=UTC).isoformat()
    else:
        booking_end_iso = booking_end_time.astimezone(UTC).isoformat()

    NotificationService.send_notification(
        db=db,
        user=current_user,
        title="Booking Reminder",
        message=(
            f"Reminder: your booking #{booking.id} at {station_name} is valid until "
            f"{booking_end_iso}"
        ),
        type="info",
        channel="push",
        category="transactional",
    )
    return {"message": "Reminder sent", "booking_id": booking.id}


@router.post("/{booking_id}/pay", response_model=BookingPaymentResponse)
async def pay_for_booking(
    booking_id: int,
    payment_in: BookingPaymentRequest | None = None,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Settle booking amount via wallet and move reservation to ACTIVE."""
    booking = _get_user_booking_or_404(db, booking_id, current_user.id)
    BookingService.mark_expired_if_due(db, booking)

    booking_status = (booking.status or "").strip().upper()
    if booking_status == "ACTIVE":
        return BookingPaymentResponse(
            booking_id=booking.id,
            status=booking.status,
            amount_paid=0.0,
            wallet_balance=float(db.exec(select(Wallet.balance).where(Wallet.user_id == current_user.id)).first() or 0.0),
            transaction_id=0,
            message="Booking already paid",
        )
    if booking_status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Cannot pay for booking in {booking_status} state")

    payment_method = (payment_in.payment_method if payment_in else "wallet").strip().lower()
    if payment_method != "wallet":
        raise HTTPException(status_code=400, detail="Only wallet payment is currently supported for bookings")

    configured_amount = float(getattr(settings, "BOOKING_RESERVATION_FEE_INR", 49.0) or 49.0)
    amount = float(payment_in.amount) if payment_in and payment_in.amount is not None else configured_amount
    amount = round(amount, 2)

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")
    if amount > 100000:
        raise HTTPException(status_code=400, detail="Payment amount exceeds allowed limit")

    wallet = db.exec(select(Wallet).where(Wallet.user_id == current_user.id)).first()
    if not wallet:
        wallet = Wallet(user_id=current_user.id, balance=0.0)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)

    if wallet.is_frozen:
        raise HTTPException(status_code=403, detail="Wallet is frozen")

    current_balance = float(wallet.balance or 0.0)
    if current_balance < amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient wallet balance. Required {amount:.2f}, available {current_balance:.2f}. "
                "Please recharge your wallet."
            ),
        )

    wallet.balance = round(current_balance - amount, 2)
    wallet.updated_at = datetime.utcnow()

    transaction = Transaction(
        user_id=current_user.id,
        wallet_id=wallet.id,
        amount=amount,
        currency=wallet.currency or "INR",
        transaction_type=TransactionType.RENTAL_PAYMENT,
        status=TransactionStatus.SUCCESS,
        payment_method=payment_method,
        description=f"Booking payment for reservation #{booking.id}",
    )

    booking.status = "ACTIVE"
    booking.updated_at = datetime.utcnow()

    db.add(wallet)
    db.add(transaction)
    db.add(booking)
    db.commit()
    db.refresh(wallet)
    db.refresh(transaction)
    db.refresh(booking)

    return BookingPaymentResponse(
        booking_id=booking.id,
        status=booking.status,
        amount_paid=amount,
        wallet_balance=float(wallet.balance),
        transaction_id=transaction.id,
        message="Booking payment successful",
    )
