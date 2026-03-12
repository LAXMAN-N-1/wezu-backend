from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, date
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

class DemandForecast(SQLModel, table=True):
    __tablename__ = "demand_forecasts"
    # __table_args__ = {"schema": "public"}
    """Predicted demand per station/region"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    forecast_type: str  # STATION, REGION, CITY, OVERALL
    entity_id: Optional[int] = None  # Station ID or Region ID
    entity_name: str
    
    forecast_date: date = Field(index=True)
    forecast_hour: Optional[int] = None  # 0-23 for hourly forecasts
    
    # Demand predictions
    predicted_rentals: int = Field(default=0)
    predicted_swaps: int = Field(default=0)
    predicted_purchases: int = Field(default=0)
    
    # Confidence intervals
    confidence_level: float = Field(default=0.95)  # 95% confidence
    lower_bound: int = Field(default=0)
    upper_bound: int = Field(default=0)
    
    # Actual vs predicted (filled after the fact)
    actual_rentals: Optional[int] = None
    actual_swaps: Optional[int] = None
    actual_purchases: Optional[int] = None
    
    forecast_accuracy: Optional[float] = None  # Calculated after actual data available
    
    # Model metadata
    model_version: str = Field(default="v1.0")
    model_features: Optional[dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChurnPrediction(SQLModel, table=True):
    __tablename__ = "churn_predictions"
    # __table_args__ = {"schema": "public"}
    """User churn risk scores"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Churn probability
    churn_probability: float = Field(default=0.0)  # 0-1
    churn_risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Contributing factors
    days_since_last_activity: int = Field(default=0)
    days_since_last_rental: Optional[int] = None
    total_rentals: int = Field(default=0)
    total_spend: float = Field(default=0.0)
    
    # Engagement metrics
    app_opens_last_30_days: int = Field(default=0)
    searches_last_30_days: int = Field(default=0)
    support_tickets_last_30_days: int = Field(default=0)
    
    # Behavioral signals
    has_unresolved_issues: bool = Field(default=False)
    has_negative_reviews: bool = Field(default=False)
    payment_failures_count: int = Field(default=0)
    
    # Feature importance
    top_churn_factors: Optional[dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    # Retention recommendations
    recommended_actions: Optional[dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    # e.g., {"offer_discount": true, "send_win_back_email": true, "assign_account_manager": false}
    
    # Action tracking
    retention_action_taken: Optional[str] = None
    retention_action_date: Optional[datetime] = None
    
    # Outcome tracking
    did_churn: Optional[bool] = None
    churn_date: Optional[date] = None
    
    # Model metadata
    model_version: str = Field(default="v1.0")
    prediction_date: date = Field(default_factory=date.today)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: "User" = Relationship()

class PricingRecommendation(SQLModel, table=True):
    __tablename__ = "pricing_recommendations"
    # __table_args__ = {"schema": "public"}
    """Dynamic pricing suggestions"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    recommendation_type: str  # RENTAL, PURCHASE, SWAP, LATE_FEE
    entity_type: str  # STATION, REGION, BATTERY_MODEL, OVERALL
    entity_id: Optional[int] = None
    
    # Current pricing
    current_price: float
    
    # Recommended pricing
    recommended_price: float
    price_change_percentage: float
    
    # Justification
    demand_factor: float = Field(default=1.0)  # Multiplier based on demand
    competition_factor: float = Field(default=1.0)  # Based on competitor pricing
    seasonality_factor: float = Field(default=1.0)  # Time-based adjustments
    inventory_factor: float = Field(default=1.0)  # Stock availability
    
    # Expected impact
    expected_revenue_change_percentage: Optional[float] = None
    expected_volume_change_percentage: Optional[float] = None
    
    # Confidence and risk
    confidence_score: float = Field(default=0.0)  # 0-100
    risk_level: str = Field(default="MEDIUM")  # LOW, MEDIUM, HIGH
    
    # Validity period
    valid_from: datetime
    valid_until: datetime
    
    # Implementation status
    status: str = Field(default="PENDING")  # PENDING, APPROVED, REJECTED, IMPLEMENTED
    implemented_at: Optional[datetime] = None
    implemented_by: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Actual results (filled after implementation)
    actual_revenue_change: Optional[float] = None
    actual_volume_change: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
