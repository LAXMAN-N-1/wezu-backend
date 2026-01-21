"""
Analytics-related Pydantic schemas
Advanced analytics, forecasting, and insights
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, date

# Request Models
class AnalyticsDateRange(BaseModel):
    """Date range for analytics"""
    start_date: date
    end_date: date
    granularity: str = Field("DAILY", pattern=r'^(HOURLY|DAILY|WEEKLY|MONTHLY)$')

class DemandForecastRequest(BaseModel):
    """Request demand forecast"""
    station_id: Optional[int] = None
    region: Optional[str] = None
    city: Optional[str] = None
    forecast_days: int = Field(7, ge=1, le=90)
    include_confidence_intervals: bool = True

class ChurnPredictionRequest(BaseModel):
    """Request churn prediction"""
    user_ids: Optional[List[int]] = None
    min_risk_level: str = Field("MEDIUM", pattern=r'^(LOW|MEDIUM|HIGH)$')
    include_recommendations: bool = True

class PricingOptimizationRequest(BaseModel):
    """Request pricing optimization"""
    battery_model: Optional[str] = None
    region: Optional[str] = None
    rental_duration_days: Optional[int] = None
    factors: List[str] = Field(
        ["DEMAND", "COMPETITION", "SEASONALITY"],
        description="Factors to consider"
    )

# Response Models
class RevenueAnalyticsResponse(BaseModel):
    """Revenue analytics"""
    total_revenue: float
    rental_revenue: float
    purchase_revenue: float
    swap_fee_revenue: float
    late_fee_revenue: float
    revenue_by_period: List[Dict]  # [{period, amount}]
    revenue_by_station: List[Dict]
    revenue_by_battery_model: List[Dict]
    growth_rate: float
    average_transaction_value: float

class UserAnalyticsResponse(BaseModel):
    """User analytics"""
    total_users: int
    active_users: int
    new_users_period: int
    churned_users: int
    user_growth_rate: float
    users_by_segment: Dict
    average_lifetime_value: float
    retention_rate: float
    engagement_metrics: Dict

class RentalAnalyticsResponse(BaseModel):
    """Rental analytics"""
    total_rentals: int
    active_rentals: int
    completed_rentals: int
    average_rental_duration_days: float
    rental_completion_rate: float
    rentals_by_battery_model: List[Dict]
    rentals_by_station: List[Dict]
    peak_rental_hours: List[int]
    utilization_rate: float

class BatteryAnalyticsResponse(BaseModel):
    """Battery analytics"""
    total_batteries: int
    available_batteries: int
    in_use_batteries: int
    maintenance_batteries: int
    average_battery_health: float
    battery_utilization_rate: float
    batteries_by_model: Dict
    batteries_by_station: Dict
    swap_frequency: Dict
    battery_lifecycle_metrics: Dict

class StationAnalyticsResponse(BaseModel):
    """Station analytics"""
    total_stations: int
    active_stations: int
    average_rating: float
    total_capacity: int
    current_occupancy: int
    occupancy_rate: float
    stations_by_performance: List[Dict]
    peak_usage_times: List[Dict]
    revenue_by_station: List[Dict]

class DemandForecastResponse(BaseModel):
    """Demand forecast response"""
    id: int
    forecast_date: date
    station_id: Optional[int]
    region: Optional[str]
    city: Optional[str]
    predicted_demand_hourly: List[float]
    predicted_demand_daily: float
    confidence_lower: Optional[float]
    confidence_upper: Optional[float]
    confidence_level: float
    model_name: str
    model_version: str
    accuracy_score: Optional[float]
    generated_at: datetime

    class Config:
        from_attributes = True

class ChurnPredictionResponse(BaseModel):
    """Churn prediction response"""
    id: int
    user_id: int
    user_email: Optional[str]
    churn_probability: float
    risk_level: str
    contributing_factors: List[str]
    factor_importance: Dict
    recommended_actions: List[str]
    prediction_date: date
    model_version: str
    confidence_score: float

    class Config:
        from_attributes = True

class PricingRecommendationResponse(BaseModel):
    """Pricing recommendation response"""
    id: int
    battery_model: Optional[str]
    region: Optional[str]
    rental_duration_days: Optional[int]
    current_price: float
    recommended_price: float
    price_change_percentage: float
    demand_elasticity: float
    competition_factor: float
    seasonality_factor: float
    inventory_factor: float
    expected_revenue_impact: float
    expected_demand_impact: float
    confidence_score: float
    risk_assessment: str
    recommendation_date: date

    class Config:
        from_attributes = True

class PerformanceDashboardResponse(BaseModel):
    """Overall performance dashboard"""
    period: str
    revenue_metrics: RevenueAnalyticsResponse
    user_metrics: UserAnalyticsResponse
    rental_metrics: RentalAnalyticsResponse
    battery_metrics: BatteryAnalyticsResponse
    station_metrics: StationAnalyticsResponse
    key_insights: List[str]
    alerts: List[Dict]
    recommendations: List[str]

class CohortAnalysisResponse(BaseModel):
    """Cohort analysis"""
    cohort_name: str
    cohort_date: date
    total_users: int
    retention_by_period: List[Dict]  # [{period, retained_users, retention_rate}]
    revenue_by_period: List[Dict]
    average_lifetime_value: float
    churn_rate: float

class FunnelAnalyticsResponse(BaseModel):
    """Conversion funnel analytics"""
    funnel_name: str
    total_entered: int
    stages: List[Dict]  # [{stage, count, conversion_rate, drop_off_rate}]
    overall_conversion_rate: float
    average_time_to_convert: Optional[float]
    bottlenecks: List[str]

class GeographicAnalyticsResponse(BaseModel):
    """Geographic analytics"""
    region: str
    total_users: int
    total_revenue: float
    total_rentals: int
    total_stations: int
    market_penetration: float
    growth_rate: float
    top_cities: List[Dict]
    heatmap_data: List[Dict]  # [{lat, lng, intensity}]
