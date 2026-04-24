from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.models.user import User
from app.schemas.analytics.logistics import LogisticsOverviewResponse
from app.services.analytics.logistics_service import analytics_logistics_service

router = APIRouter()

@router.get("/overview", response_model=LogisticsOverviewResponse)
async def get_logistics_overview(
    period: str = Query("30d", description="Filter period: 7d, 30d, 90d, 365d, weekly, monthly, yearly"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_driver_or_internal_operator)
):
    return await analytics_logistics_service.get_overview(db, period)
