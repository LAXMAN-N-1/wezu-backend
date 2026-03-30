from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel
from app.api import deps
from app.models.user import User
from app.models.rental import Rental, Purchase, RentalStatus
from app.models.swap import SwapSession
from app.models.late_fee import LateFee, LateFeeWaiver
from app.core.database import get_db

router = APIRouter()

# --- Schemas ---

class WaiverReviewRequest(BaseModel):
    status: str  # APPROVED, REJECTED
    approved_amount: Optional[float] = None
    admin_notes: Optional[str] = None

# --- Dashboard Stats ---

@router.get("/stats")
def get_rental_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get high-level statistics for rentals and orders."""
    total_active = db.exec(select(func.count(Rental.id)).where(Rental.status == RentalStatus.ACTIVE)).one()
    overdue_count = db.exec(select(func.count(Rental.id)).where(Rental.status == RentalStatus.OVERDUE)).one()
    total_swaps = db.exec(select(func.count(SwapSession.id))).one()
    
    # Simple revenue calculation for today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_revenue = db.exec(select(func.sum(Rental.total_amount)).where(Rental.created_at >= today_start)).one() or 0.0
    
    return {
        "active_rentals": total_active,
        "overdue_rentals": overdue_count,
        "total_swaps_completed": total_swaps,
        "today_revenue": round(float(today_revenue), 2),
    }

# --- Rentals ---

@router.get("/active")
def list_active_rentals(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List all currently active rentals."""
    statement = select(Rental).where(Rental.status == RentalStatus.ACTIVE).offset(skip).limit(limit)
    rentals = db.exec(statement).all()
    
    result = []
    for r in rentals:
        user = db.get(User, r.user_id)
        result.append({
            "id": r.id,
            "user_name": user.full_name if user else "Unknown",
            "battery_id": r.battery_id,
            "start_time": r.start_time,
            "expected_end_time": r.expected_end_time,
            "total_amount": r.total_amount,
            "battery_level": r.start_battery_level
        })
    return result

@router.get("/history")
def list_rental_history(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List completed/cancelled rentals with search."""
    statement = select(Rental).where(Rental.status.in_([RentalStatus.COMPLETED, RentalStatus.CANCELLED]))
    
    # In a real app, search might join User table. For now simplified:
    statement = statement.order_by(Rental.end_time.desc()).offset(skip).limit(limit)
    rentals = db.exec(statement).all()
    
    result = []
    for r in rentals:
        user = db.get(User, r.user_id)
        result.append({
            "id": r.id,
            "user_name": user.full_name if user else "Unknown",
            "start_time": r.start_time,
            "end_time": r.end_time,
            "total_amount": r.total_amount,
            "status": r.status
        })
    return result

# --- Swaps ---

@router.get("/swaps")
def list_swaps(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List battery swap sessions."""
    statement = select(SwapSession).order_by(SwapSession.created_at.desc()).offset(skip).limit(limit)
    swaps = db.exec(statement).all()
    
    result = []
    for s in swaps:
        user = db.get(User, s.user_id)
        result.append({
            "id": s.id,
            "user_name": user.full_name if user else "Unknown",
            "station_id": s.station_id,
            "old_battery_soc": s.old_battery_soc,
            "new_battery_soc": s.new_battery_soc,
            "status": s.status,
            "created_at": s.created_at
        })
    return result

# --- Purchases ---

@router.get("/purchases")
def list_purchases(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List battery purchase orders."""
    statement = select(Purchase).order_by(Purchase.timestamp.desc()).offset(skip).limit(limit)
    purchases = db.exec(statement).all()
    
    result = []
    for p in purchases:
        user = db.get(User, p.user_id)
        result.append({
            "id": p.id,
            "user_name": user.full_name if user else "Unknown",
            "battery_id": p.battery_id,
            "amount": p.amount,
            "timestamp": p.timestamp
        })
    return result

# --- Late Fees ---

@router.get("/late-fees")
def list_late_fees(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List all late fees and associated waiver requests."""
    late_fees = db.exec(select(LateFee).order_by(LateFee.created_at.desc())).all()
    
    result = []
    for lf in late_fees:
        user = db.get(User, lf.user_id)
        # Check for waiver
        waiver = db.exec(select(LateFeeWaiver).where(LateFeeWaiver.late_fee_id == lf.id)).first()
        
        result.append({
            "id": lf.id,
            "user_name": user.full_name if user else "Unknown",
            "days_overdue": lf.days_overdue,
            "total_late_fee": lf.total_late_fee,
            "payment_status": lf.payment_status,
            "waiver_status": waiver.status if waiver else "NONE",
            "waiver_id": waiver.id if waiver else None,
            "created_at": lf.created_at
        })
    return result

@router.put("/late-fees/waivers/{waiver_id}/review")
def review_waiver(
    waiver_id: int,
    request: WaiverReviewRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Approve or reject a late fee waiver request."""
    waiver = db.get(LateFeeWaiver, waiver_id)
    if not waiver:
        raise HTTPException(status_code=404, detail="Waiver request not found")
    
    waiver.status = request.status
    waiver.admin_notes = request.admin_notes
    waiver.reviewed_by = current_user.id
    waiver.reviewed_at = datetime.utcnow()
    
    if request.status == "APPROVED" and request.approved_amount is not None:
        waiver.approved_waiver_amount = request.approved_amount
        # Update corresponding late fee
        late_fee = db.get(LateFee, waiver.late_fee_id)
        if late_fee:
            late_fee.amount_waived = request.approved_amount
            late_fee.amount_outstanding = max(0, late_fee.total_late_fee - late_fee.amount_paid - request.approved_amount)
            if late_fee.amount_outstanding == 0:
                late_fee.payment_status = "WAIVED"
            db.add(late_fee)
            
    db.add(waiver)
    db.commit()
    return {"status": "success", "waiver_status": waiver.status}

@router.put("/{rental_id}/terminate")
def terminate_rental(
    rental_id: int,
    reason: str = Query(...),
    current_user: Any = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_db),
):
    """Forcefully terminate a rental."""
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    if rental.status == RentalStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Rental already completed")
    
    rental.status = RentalStatus.CANCELLED
    rental.end_time = datetime.utcnow()
    db.add(rental)
    db.commit()
    return {"status": "success", "message": f"Rental terminated: {reason}"}
