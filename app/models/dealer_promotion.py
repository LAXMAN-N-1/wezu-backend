from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

if TYPE_CHECKING:
    from app.models.dealer import DealerProfile
    from app.models.user import User

class DealerPromotion(SQLModel, table=True):
    __tablename__ = "dealer_promotions"
    # __table_args__ = {"schema": "public"}
    """Dealer-created promotional campaigns"""
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealer_profiles.id")
    
    name: str
    description: Optional[str] = None
    promo_code: str = Field(unique=True, index=True)
    
    discount_type: str  # PERCENTAGE, FIXED_AMOUNT, FREE_DELIVERY
    discount_value: float
    
    min_purchase_amount: Optional[float] = None
    max_discount_amount: Optional[float] = None
    
    # Budget and Controls
    budget_limit: Optional[float] = None
    daily_cap: Optional[int] = None
    
    usage_limit_total: Optional[int] = None  # Total times this can be used
    usage_limit_per_user: int = Field(default=1)
    
    # Tracking
    usage_count: int = Field(default=0)
    total_discount_given: float = Field(default=0.0)
    impressions: int = Field(default=0)
    
    applicable_to: str = Field(default="ALL")  # ALL, RENTAL, PURCHASE, SPECIFIC_MODELS
    applicable_station_ids: Optional[str] = None  # JSON array of station IDs

    applicable_models: Optional[str] = None  # JSON array of battery models
    
    start_date: datetime
    end_date: datetime
    
    is_active: bool = Field(default=True)
    requires_approval: bool = Field(default=True)  # Admin approval required
    approved_by: Optional[int] = Field(default=None, foreign_key="users.id")
    approved_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    dealer: "DealerProfile" = Relationship()
    usages: list["PromotionUsage"] = Relationship(back_populates="promotion")

class PromotionUsage(SQLModel, table=True):
    __tablename__ = "promotion_usages"
    # __table_args__ = {"schema": "public"}
    """Track promotion redemptions"""
    id: Optional[int] = Field(default=None, primary_key=True)
    promotion_id: int = Field(foreign_key="dealer_promotions.id")
    user_id: int = Field(foreign_key="users.id")
    
    order_id: Optional[int] = Field(default=None, foreign_key="ecommerce_orders.id")
    rental_id: Optional[int] = Field(default=None, foreign_key="rentals.id")
    
    discount_applied: float
    original_amount: float
    final_amount: float
    
    used_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    promotion: DealerPromotion = Relationship(back_populates="usages")
    user: "User" = Relationship()
