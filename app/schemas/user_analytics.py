"""
User Analytics Schemas — Personal Cost Analytics & Trends
Shared file: Task 7 (Cost Analytics) + Task 8 (Battery Usage Stats)
"""
from pydantic import BaseModel, Field
from typing import List, Optional


# ─── Cost Analytics (Task 7) ────────────────────────────────────────

class CostBreakdown(BaseModel):
    """Rental vs purchase breakdown"""
    rentals: float = 0.0
    purchases: float = 0.0


class CostTrendItem(BaseModel):
    """Single month in the trend chart"""
    month: str = Field(..., description="YYYY-MM format")
    rentals: float = 0.0
    purchases: float = 0.0


class PeriodComparison(BaseModel):
    """Current period vs previous period"""
    current: float = 0.0
    previous: float = 0.0
    change_percent: float = 0.0


class CostAnalyticsSummary(BaseModel):
    """Full cost analytics response"""
    total_spent_this_month: float = 0.0
    total_spent_this_year: float = 0.0
    total_spent_lifetime: float = 0.0
    avg_monthly_spending: float = 0.0
    breakdown: CostBreakdown = CostBreakdown()
    month_over_month_change: float = 0.0
    trends: List[CostTrendItem] = []
    comparison_with_previous_period: PeriodComparison = PeriodComparison()


class CostTrendsResponse(BaseModel):
    """Monthly trend chart data only"""
    trends: List[CostTrendItem] = []


# ─── Battery Usage Stats (Task 8) ────────────────────────────────────

class FavoriteStation(BaseModel):
    """Most-visited station"""
    id: Optional[int] = None
    name: Optional[str] = None
    rental_count: int = 0


class UsagePatterns(BaseModel):
    """Usage distribution by day-of-week and hour-of-day"""
    by_day_of_week: dict = {}
    by_hour_of_day: dict = {}
    peak_usage_day: Optional[str] = None
    peak_usage_hour: Optional[str] = None


class UsageStatsResponse(BaseModel):
    """Full battery usage statistics response"""
    total_batteries_rented: int = 0
    total_batteries_purchased: int = 0
    avg_rental_duration_hours: float = 0.0
    longest_rental_hours: float = 0.0
    most_rented_battery_type: Optional[str] = None
    usage_patterns: UsagePatterns = UsagePatterns()
    carbon_saved_kg: float = 0.0
    favorite_station: FavoriteStation = FavoriteStation()
    current_streak_days: int = 0
    badges_earned: List[str] = []

