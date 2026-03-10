from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.models.battery_reservation import BatteryReservation
from app.services.booking_service import BookingService
from app.schemas.booking import BookingCreate, BookingResponse, BookingUpdate

router = APIRouter()

@router.post("/", response_model=BookingResponse)
async def create_booking(
    booking_in: BookingCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Create a new battery reservation"""
    try:
        return BookingService.create_reservation(db, current_user.id, booking_in.station_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[BookingResponse])
async def list_my_bookings(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """List current user's reservations"""
    statement = select(BatteryReservation).where(BatteryReservation.user_id == current_user.id)
    return db.exec(statement).all()

@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_details(
    booking_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get reservation details"""
    booking = db.get(BatteryReservation, booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking

@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: int,
    booking_in: BookingUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Update reservation status"""
    booking = db.get(BatteryReservation, booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking_in.status:
        booking.status = booking_in.status
    
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
    """Cancel reservation"""
    booking = db.get(BatteryReservation, booking_id)
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking.status = "CANCELLED"
    db.add(booking)
    db.commit()
    return {"message": "Booking cancelled"}

@router.post("/{booking_id}/reminder")
async def send_booking_reminder(
    booking_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Send reminder notification for booking"""
    from app.services.notification_service import NotificationService
    NotificationService.send_notification(
        db=db,
        user_id=current_user.id,
        title="Booking Reminder",
        message=f"Reminder for your booking {booking_id}"
    )
    return {"message": "Reminder sent"}

@router.post("/{booking_id}/pay")
async def pay_for_booking(
    booking_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Process payment for booking"""
    # This is a placeholder for actual payment processing
    return {"message": "Payment successful", "booking_id": booking_id}
