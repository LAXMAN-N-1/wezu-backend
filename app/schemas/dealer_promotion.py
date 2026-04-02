"""
Dealer Promotion schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime


class DealerPromotionCreate(BaseModel):
    promo_code: str = Field(..., min_length=4, max_length=20)
    description: str
    discount_type: str  # PERCENTAGE, FIXED_AMOUNT, FREE_DELIVERY
    discount_value: float = Field(..., gt=0)
    start_date: datetime
    end_date: datetime
    max_usage_total: Optional[int] = None
    max_usage_per_user: int = 1
    min_order_value: Optional[float] = None
    applicable_battery_models: Optional[List[str]] = None
    applicable_to_rental: bool = True
    applicable_to_purchase: bool = True

class DealerPromotionUpdate(BaseModel):
    description: Optional[str] = None
    discount_value: Optional[float] = None
    end_date: Optional[datetime] = None
    max_usage_total: Optional[int] = None
    is_active: Optional[bool] = None

class DealerPromotionResponse(BaseModel):
    id: int
    dealer_id: int
    promo_code: str
    description: str
    discount_type: str
    discount_value: float
    start_date: datetime
    end_date: datetime
    is_active: bool = True
    max_usage_total: Optional[int] = None
    current_usage_count: int = 0
    max_usage_per_user: int = 1
    min_order_value: Optional[float] = None
    applicable_battery_models: Optional[List[str]] = None
    applicable_to_rental: bool = True
    applicable_to_purchase: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PromotionUsageResponse(BaseModel):
    id: int
    promotion_id: int
    user_id: int
    order_id: Optional[int] = None
    discount_amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DealerPromotionListResponse(BaseModel):
    promotions: List[DealerPromotionResponse]
    total_count: int
