from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum

class SettlementStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Settlement(SQLModel, table=True):
    __tablename__ = "settlements"
    __table_args__ = {"schema": "finance"}
    id: Optional[int] = Field(default=None, primary_key=True)
    
    dealer_id: int = Field(foreign_key="dealers.dealer_profiles.id", index=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="finance.vendors.id")
    
    amount: float
    currency: str = Field(default="INR")
    
    status: SettlementStatus = Field(default=SettlementStatus.PENDING)
    
    payment_method: str = Field(default="bank_transfer")
    payment_reference: Optional[str] = None
    
    period_start: datetime
    period_end: datetime
    
    processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    dealer: "DealerProfile" = Relationship(back_populates="settlements")
    commission_logs: List["CommissionLog"] = Relationship(back_populates="settlement")
