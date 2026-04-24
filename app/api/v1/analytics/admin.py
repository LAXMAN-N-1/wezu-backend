from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.models.user import User
from app.schemas.analytics.admin import AdminOverviewResponse
from app.services.analytics.admin_service import analytics_admin_service

router = APIRouter()

@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(
    period: str = Query("30d", description="Filter period: 7d, 30d, 90d, 365d, weekly, monthly, yearly"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    Get the Hawk-Eye dashboard overview for Super Admins.
    """
    return await analytics_admin_service.get_overview(db, period)
