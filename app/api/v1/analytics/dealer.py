from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.models.user import User
from app.schemas.analytics.dealer import DealerOverviewResponse
from app.services.analytics.dealer_service import analytics_dealer_service

router = APIRouter()

@router.get("/overview", response_model=DealerOverviewResponse)
async def get_dealer_overview(
    period: str = Query("30d", description="Filter period: 7d, 30d, 90d, 365d, weekly, monthly, yearly"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    return await analytics_dealer_service.get_overview(db, period)
