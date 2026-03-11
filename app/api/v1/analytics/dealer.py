from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.models.user import User
from app.schemas.analytics.dealer import DealerOverviewResponse
from app.services.analytics.dealer_service import analytics_dealer_service

from app.models.dealer import DealerProfile

router = APIRouter()

@router.get("/overview", response_model=DealerOverviewResponse)
async def get_dealer_overview(
    period: str = Query("30d", description="Filter period: 7d, 30d, 90d, 365d, weekly, monthly, yearly"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    dealer_profile = db.query(DealerProfile).filter(DealerProfile.user_id == current_user.id).first()
    d_id = dealer_profile.id if dealer_profile else None
    return await analytics_dealer_service.get_overview(db, period, dealer_profile_id=d_id)
