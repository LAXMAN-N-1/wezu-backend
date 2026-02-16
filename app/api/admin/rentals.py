from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime
from app.api import deps
from app.models.user import User
from app.models.rental import Rental
from app.schemas.rental import RentalResponse
from app.db.session import get_session

router = APIRouter()

@router.get("/", response_model=List[RentalResponse])
def list_rentals(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """List all rentals with filters."""
    statement = select(Rental)
    if status:
        statement = statement.where(Rental.status == status)
    if user_id:
        statement = statement.where(Rental.user_id == user_id)
    
    statement = statement.offset(skip).limit(limit).order_by(Rental.created_at.desc())
    rentals = db.exec(statement).all()
    return rentals

@router.put("/{rental_id}/terminate")
def terminate_rental(
    rental_id: int,
    reason: str = Query(...),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(get_session),
):
    """Forcefully terminate a rental."""
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    if rental.status == "completed":
        raise HTTPException(status_code=400, detail="Rental already completed")
    
    rental.status = "terminated"
    rental.end_time = datetime.utcnow()
    # Logic to release battery/slot could be added here or via service
    db.add(rental)
    db.commit()
    return {"status": "success", "message": f"Rental terminated: {reason}"}
