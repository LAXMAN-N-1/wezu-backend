from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.api import deps
from app.models.user import User

router = APIRouter()

# --- Global Stats (Aggregated across modules) ---
@router.get("/stats")
async def get_admin_stats(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
):
    from app.models.station import Station
    from app.models.battery import Battery
    from app.models.rental import Rental
    from app.models.kyc import KYCDocument
    
    total_users = len(db.exec(select(User)).all())
    total_stations = len(db.exec(select(Station)).all())
    total_batteries = len(db.exec(select(Battery)).all())
    active_rentals = len(db.exec(select(Rental).where(Rental.status == "active")).all())
    pending_kyc = len(db.exec(select(KYCDocument).where(KYCDocument.status == "pending")).all())
    
    return {
        "total_users": total_users,
        "total_stations": total_stations,
        "total_batteries": total_batteries,
        "active_rentals": active_rentals,
        "pending_kyc": pending_kyc
    }
