from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import List
from app.api import deps
from app.models.user import User
from app.core.config import settings
from app.utils.runtime_cache import cached_call

router = APIRouter()

# --- Global Stats (Aggregated across modules) ---
@router.get("/stats")
def get_admin_stats(
    current_user: User = Depends(deps.get_current_active_admin),
    db: Session = Depends(deps.get_db),
):
    def _load():
        from app.models.station import Station
        from app.models.battery import Battery
        from app.models.rental import Rental
        from app.models.kyc import KYCDocument

        total_users = db.exec(select(func.count(User.id))).one()
        total_stations = db.exec(select(func.count(Station.id))).one()
        total_batteries = db.exec(select(func.count(Battery.id))).one()
        active_rentals = db.exec(select(func.count(Rental.id)).where(Rental.status == "active")).one()
        pending_kyc = db.exec(select(func.count(KYCDocument.id)).where(KYCDocument.status == "pending")).one()

        return {
            "total_users": total_users,
            "total_stations": total_stations,
            "total_batteries": total_batteries,
            "active_rentals": active_rentals,
            "pending_kyc": pending_kyc
        }

    return cached_call("admin-main", "stats", ttl_seconds=settings.ANALYTICS_CACHE_TTL_SECONDS, call=_load)
