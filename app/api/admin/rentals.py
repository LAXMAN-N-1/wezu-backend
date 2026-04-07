from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional, Any
from datetime import datetime, UTC
from pydantic import BaseModel
from app.api import deps
from app.models.user import User
from app.models.rental import Rental, Purchase, RentalStatus
from app.models.swap import SwapSession
from app.models.late_fee import LateFee, LateFeeWaiver
from app.core.database import get_db
from app.core.config import settings
from app.utils.runtime_cache import cached_call

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
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Get high-level statistics for rentals and orders."""
    def _load():
        total_active = db.exec(select(func.count(Rental.id)).where(Rental.status == RentalStatus.ACTIVE)).one()
        overdue_count = db.exec(select(func.count(Rental.id)).where(Rental.status == RentalStatus.OVERDUE)).one()
        total_swaps = db.exec(select(func.count(SwapSession.id))).one()

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_revenue = db.exec(select(func.sum(Rental.total_amount)).where(Rental.created_at >= today_start)).one() or 0.0

        return {
            "active_rentals": total_active,
            "overdue_rentals": overdue_count,
            "total_swaps_completed": total_swaps,
            "today_revenue": round(float(today_revenue), 2),
        }

    return cached_call("admin-rentals", "stats", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)

# --- Rentals ---

@router.get("/active")
def list_active_rentals(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List all currently active rentals."""
    statement = select(Rental).where(Rental.status == RentalStatus.ACTIVE).offset(skip).limit(limit)
    rentals = db.exec(statement).all()
    
    user_ids = {r.user_id for r in rentals if r.user_id}
    users = db.exec(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    user_map = {u.id: u for u in users}

    result = []
    for r in rentals:
        user = user_map.get(r.user_id)
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
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List completed/cancelled rentals with search."""
    statement = select(Rental).where(Rental.status.in_([RentalStatus.COMPLETED, RentalStatus.CANCELLED]))
    
    # In a real app, search might join User table. For now simplified:
    statement = statement.order_by(Rental.end_time.desc()).offset(skip).limit(limit)
    rentals = db.exec(statement).all()
    
    user_ids = {r.user_id for r in rentals if r.user_id}
    users = db.exec(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    user_map = {u.id: u for u in users}

    result = []
    for r in rentals:
        user = user_map.get(r.user_id)
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
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List battery swap sessions."""
    statement = select(SwapSession).order_by(SwapSession.created_at.desc()).offset(skip).limit(limit)
    swaps = db.exec(statement).all()
    
    user_ids = {s.user_id for s in swaps if s.user_id}
    user_map = {u.id: u.full_name for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    result = []
    for s in swaps:
        result.append({
            "id": s.id,
            "user_name": user_map.get(s.user_id, "Unknown"),
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
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List battery purchase orders."""
    statement = select(Purchase).order_by(Purchase.timestamp.desc()).offset(skip).limit(limit)
    purchases = db.exec(statement).all()
    
    user_ids = {p.user_id for p in purchases if p.user_id}
    user_map = {u.id: u.full_name for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    result = []
    for p in purchases:
        result.append({
            "id": p.id,
            "user_name": user_map.get(p.user_id, "Unknown"),
            "battery_id": p.battery_id,
            "amount": p.amount,
            "timestamp": p.timestamp
        })
    return result

# --- Late Fees ---

@router.get("/late-fees")
def list_late_fees(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List all late fees and associated waiver requests."""
    late_fees = db.exec(select(LateFee).order_by(LateFee.created_at.desc())).all()
    
    user_ids = {lf.user_id for lf in late_fees if lf.user_id}
    user_map = {u.id: u.full_name for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    lf_ids = {lf.id for lf in late_fees}
    waiver_map = {w.late_fee_id: w for w in db.exec(select(LateFeeWaiver).where(LateFeeWaiver.late_fee_id.in_(lf_ids))).all()} if lf_ids else {}

    result = []
    for lf in late_fees:
        waiver = waiver_map.get(lf.id)
        result.append({
            "id": lf.id,
            "user_name": user_map.get(lf.user_id, "Unknown"),
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
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Approve or reject a late fee waiver request."""
    waiver = db.get(LateFeeWaiver, waiver_id)
    if not waiver:
        raise HTTPException(status_code=404, detail="Waiver request not found")
    
    waiver.status = request.status
    waiver.admin_notes = request.admin_notes
    waiver.reviewed_by = current_user.id
    waiver.reviewed_at = datetime.now(UTC)
    
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
    current_user: Any = Depends(deps.get_current_active_admin),
    db: Session = Depends(get_db),
):
    """Forcefully terminate a rental."""
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    if rental.status == RentalStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Rental already completed")
    
    rental.status = RentalStatus.CANCELLED
    rental.end_time = datetime.now(UTC)
    db.add(rental)
    db.commit()
    return {"status": "success", "message": f"Rental terminated: {reason}"}
