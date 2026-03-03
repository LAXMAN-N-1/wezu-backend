from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api import deps
from app.models.user import User
from app.schemas.analytics.customer import CustomerOverviewResponse
from app.services.analytics.customer_service import analytics_customer_service

router = APIRouter()

@router.get("/overview", response_model=CustomerOverviewResponse)
async def get_customer_overview(
    period: str = Query("30d", description="Filter period: 7d, 30d, 90d, 365d, weekly, monthly, yearly"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
):
    return await analytics_customer_service.get_overview(db, period)
