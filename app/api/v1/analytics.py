"""
Customer Analytics and Dashboard API
Personal stats, usage patterns, and insights
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.schemas.common import DataResponse

router = APIRouter()

@router.get("/dashboard", response_model=DataResponse[dict])
def get_dashboard(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get customer dashboard
    Shows active rentals, spending, favorite stations, etc.
    """
    dashboard = AnalyticsService.get_customer_dashboard(current_user.id, session)
    
    return DataResponse(
        success=True,
        data=dashboard
    )

@router.get("/rental-history", response_model=DataResponse[dict])
def get_rental_history_stats(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get rental history statistics"""
    stats = AnalyticsService.get_rental_history_stats(current_user.id, session)
    
    return DataResponse(
        success=True,
        data=stats
    )

@router.get("/cost-analytics", response_model=DataResponse[dict])
def get_cost_analytics(
    months: int = Query(3, ge=1, le=12),
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get cost analytics
    Monthly breakdown of spending
    """
    analytics = AnalyticsService.get_cost_analytics(current_user.id, months, session)
    
    return DataResponse(
        success=True,
        data=analytics
    )

@router.get("/usage-patterns", response_model=DataResponse[dict])
def get_usage_patterns(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get usage patterns
    Most active day/hour, average duration, etc.
    """
    patterns = AnalyticsService.get_usage_patterns(current_user.id, session)
    
    return DataResponse(
        success=True,
        data=patterns
    )
