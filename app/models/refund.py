from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC

class Refund(SQLModel, table=True):
    __tablename__ = "refunds"
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: int = Field(foreign_key="transactions.id")
    amount: float
    reason: Optional[str] = None
    status: str = Field(default="pending") # pending, processed, failed
    gateway_refund_id: Optional[str] = None # Razorpay refund ID
    
    processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    transaction: "Transaction" = Relationship(back_populates="refund")
