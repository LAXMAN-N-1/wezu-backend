from __future__ import annotations
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, timezone; UTC = timezone.utc

class PromoCode(SQLModel, table=True):
    __tablename__ = "promo_codes"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    description: Optional[str] = None
    discount_amount: float = Field(default=0.0) # Flat discount
    discount_percentage: float = Field(default=0.0) # % discount
    max_discount_amount: Optional[float] = None
    min_order_amount: float = Field(default=0.0)
    min_rental_days: int = Field(default=0)
    
    is_active: bool = Field(default=True)
    valid_from: datetime = Field(default_factory=lambda: datetime.now(UTC))
    valid_until: Optional[datetime] = None
    
    usage_limit: int = Field(default=0) # 0 = unlimited
    usage_count: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
