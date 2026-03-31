"""
Personal Cost Analytics API — Customer-facing endpoints
Shared file: Task 7 (Cost Analytics) + Task 8 (Battery Usage Stats)
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from enum import Enum

from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.schemas.common import DataResponse
from app.schemas.user_analytics import CostAnalyticsSummary, CostTrendsResponse, UsageStatsResponse
from app.utils.cache import cache

router = APIRouter()


# ── Enums for query validation ──────────────────────────────────────

class PeriodEnum(str, Enum):
    THREE_MONTHS = "3m"
    SIX_MONTHS = "6m"
    ONE_YEAR = "1y"
    ALL = "all"


class TypeEnum(str, Enum):
    RENTAL = "rental"
    PURCHASE = "purchase"
    ALL = "all"


# ── Endpoints (Task 7 — Cost Analytics) ─────────────────────────────

@router.get("/me/cost-analytics", response_model=DataResponse[CostAnalyticsSummary])
@cache(expire=3600)
async def get_cost_analytics(
    period: PeriodEnum = Query(PeriodEnum.THREE_MONTHS, description="Time window"),
    type: TypeEnum = Query(TypeEnum.ALL, description="Filter by transaction type"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full personal cost analytics summary.

    Includes lifetime / yearly / monthly totals, rental vs purchase breakdown,
    month-over-month change, period comparison, and inline trend data.
    """
    data = AnalyticsService.get_personal_cost_analytics(
        db, current_user.id, period.value, type.value
    )
    return DataResponse(success=True, data=data)


@router.get("/me/cost-analytics/trends", response_model=DataResponse[CostTrendsResponse])
@cache(expire=3600)
async def get_cost_analytics_trends(
    period: PeriodEnum = Query(PeriodEnum.THREE_MONTHS, description="Time window"),
    type: TypeEnum = Query(TypeEnum.ALL, description="Filter by transaction type"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Monthly trend chart data for the requested period.

    Returns rental and purchase amounts per month suitable for chart rendering.
    """
    trends = AnalyticsService.get_personal_cost_trends(
        db, current_user.id, period.value, type.value
    )
    return DataResponse(success=True, data={"trends": trends})


# ── Endpoints (Task 8 — Battery Usage Stats) ────────────────────────

@router.get("/me/usage-stats", response_model=DataResponse[UsageStatsResponse])
@cache(expire=3600)
async def get_usage_stats(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Comprehensive battery usage statistics for the authenticated customer.

    Includes total rentals/purchases, avg/longest duration, peak usage times,
    carbon savings, favorite station, streaks, and badges.
    """
    data = AnalyticsService.get_personal_usage_stats(db, current_user.id)
    return DataResponse(success=True, data=data)

