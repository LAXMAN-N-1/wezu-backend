from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.schemas.rental import RentalCreate, RentalResponse, ActiveRentalResponse
from app.services.rental_service import RentalService

router = APIRouter()

@router.post("/", response_model=RentalResponse)
async def create_rental(
    rental_in: RentalCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    # Check if user has active rental? Logic in service or here.
    # Service doesn't check, let's assume multiple rentals allowed or enforced globally.
    return RentalService.create_rental(db, current_user.id, rental_in)

@router.get("/active", response_model=List[RentalResponse])
async def read_active_rentals(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return RentalService.get_active_rentals(db, current_user.id)

@router.get("/history", response_model=List[RentalResponse])
async def read_rental_history(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return RentalService.get_history(db, current_user.id)

@router.post("/{rental_id}/return", response_model=RentalResponse)
async def return_rental_battery(
    rental_id: int,
    station_id: int, # Pass as query param or body? Usually body. Simplifying to query for now or fix schema.
    # Let's use query param for simplicity or body if complex.
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    # Verify rental belongs to user
    # logic in service usually, but service.return_battery(rental_id) assumes valid rental_id
    # We should verify ownership here.
    rental = RentalService.return_battery(db, rental_id, station_id)
    if rental.user_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not authorized")
    return rental

# Rental Modifications
from pydantic import BaseModel
from datetime import datetime
from app.models.rental_modification import RentalExtension, RentalPause
from app.models.late_fee import LateFee, LateFeeWaiver

class ExtensionRequest(BaseModel):
    requested_end_date: datetime
    reason: Optional[str] = None

class PauseRequest(BaseModel):
    pause_start_date: datetime
    pause_end_date: datetime
    reason: str

class WaiverRequest(BaseModel):
    requested_waiver_amount: float
    reason: str
    supporting_documents: Optional[str] = None

@router.post("/{rental_id}/extend", response_model=RentalExtension)
async def request_extension(
    rental_id: int,
    req: ExtensionRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Request rental extension"""
    from app.models.rental import Rental
    from sqlmodel import select
    
    rental = db.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    if rental.status != "active":
        raise HTTPException(status_code=400, detail="Rental is not active")
    
    # Calculate extension days and cost
    extension_days = (req.requested_end_date - rental.end_date).days
    if extension_days <= 0:
        raise HTTPException(status_code=400, detail="Extension date must be after current end date")
    
    # Simple cost calculation (should be in service)
    additional_cost = extension_days * rental.daily_rate
    
    extension = RentalExtension(
        rental_id=rental_id,
        user_id=current_user.id,
        current_end_date=rental.end_date,
        requested_end_date=req.requested_end_date,
        extension_days=extension_days,
        additional_cost=additional_cost,
        reason=req.reason,
        status="PENDING"
    )
    db.add(extension)
    db.commit()
    db.refresh(extension)
    return extension

@router.post("/{rental_id}/pause", response_model=RentalPause)
async def request_pause(
    rental_id: int,
    req: PauseRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Request rental pause"""
    from app.models.rental import Rental
    
    rental = db.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    if rental.status != "active":
        raise HTTPException(status_code=400, detail="Rental is not active")
    
    pause_days = (req.pause_end_date - req.pause_start_date).days
    if pause_days <= 0:
        raise HTTPException(status_code=400, detail="Invalid pause period")
    
    # Reduced rate during pause (e.g., 20% of daily rate)
    daily_pause_charge = rental.daily_rate * 0.2
    total_pause_cost = daily_pause_charge * pause_days
    
    pause = RentalPause(
        rental_id=rental_id,
        user_id=current_user.id,
        pause_start_date=req.pause_start_date,
        pause_end_date=req.pause_end_date,
        pause_days=pause_days,
        reason=req.reason,
        daily_pause_charge=daily_pause_charge,
        total_pause_cost=total_pause_cost,
        status="PENDING"
    )
    db.add(pause)
    db.commit()
    db.refresh(pause)
    return pause

@router.post("/{rental_id}/resume")
async def resume_rental(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Resume paused rental"""
    from sqlmodel import select
    
    pause = db.exec(
        select(RentalPause)
        .where(RentalPause.rental_id == rental_id)
        .where(RentalPause.status == "ACTIVE")
    ).first()
    
    if not pause:
        raise HTTPException(status_code=404, detail="No active pause found")
    
    if pause.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    pause.status = "COMPLETED"
    pause.battery_reclaimed_at = datetime.utcnow()
    db.add(pause)
    db.commit()
    
    return {"status": "resumed", "message": "Rental resumed successfully"}

@router.get("/{rental_id}/late-fees", response_model=LateFee)
async def get_late_fees(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Get late fee details for rental"""
    from sqlmodel import select
    
    late_fee = db.exec(
        select(LateFee).where(LateFee.rental_id == rental_id)
    ).first()
    
    if not late_fee:
        raise HTTPException(status_code=404, detail="No late fees found")
    
    if late_fee.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return late_fee

@router.post("/{rental_id}/late-fees/waiver", response_model=LateFeeWaiver)
async def request_late_fee_waiver(
    rental_id: int,
    req: WaiverRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Request late fee waiver"""
    from sqlmodel import select
    
    late_fee = db.exec(
        select(LateFee).where(LateFee.rental_id == rental_id)
    ).first()
    
    if not late_fee:
        raise HTTPException(status_code=404, detail="No late fees found")
    
    if late_fee.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if late_fee.amount_outstanding == 0:
        raise HTTPException(status_code=400, detail="No outstanding late fees")
    
    waiver = LateFeeWaiver(
        late_fee_id=late_fee.id,
        user_id=current_user.id,
        requested_waiver_amount=req.requested_waiver_amount,
        reason=req.reason,
        supporting_documents=req.supporting_documents,
        status="PENDING"
    )
    db.add(waiver)
    db.commit()
    db.refresh(waiver)
    return waiver

from typing import Optional
