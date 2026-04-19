from __future__ import annotations
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
    current_user: User = Depends(deps.get_current_dealer_scope_user),
):
    dealer_profile = deps.get_dealer_profile_for_user(db, current_user)
    d_id = dealer_profile.id if dealer_profile else None
    return await analytics_dealer_service.get_overview(db, period, dealer_profile_id=d_id)
