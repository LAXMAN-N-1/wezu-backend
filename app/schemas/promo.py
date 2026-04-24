from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class PromoBase(BaseModel):
    code: str
    description: Optional[str] = None
    discount_amount: float = 0.0
    discount_percentage: float = 0.0
    max_discount_amount: Optional[float] = None
    min_order_amount: float = 0.0
    min_rental_days: int = 0
    is_active: bool = True
    valid_until: Optional[datetime] = None
    usage_limit: int = 0 # 0 = unlimited

class PromoCreate(PromoBase):
    pass

class PromoUpdate(BaseModel):
    description: Optional[str] = None
    discount_amount: Optional[float] = None
    discount_percentage: Optional[float] = None
    max_discount_amount: Optional[float] = None
    min_order_amount: Optional[float] = None
    is_active: Optional[bool] = None
    valid_until: Optional[datetime] = None
    usage_limit: Optional[int] = None

class PromoResponse(PromoBase):
    id: int
    usage_count: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
