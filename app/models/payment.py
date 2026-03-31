from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC

class PaymentTransaction(SQLModel, table=True):
    __tablename__ = "payment_transactions"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    amount: float
    currency: str = Field(default="INR")
    status: str = Field(default="pending") # pending, success, failed, refunded
    payment_method: str = "razorpay" 
    
    # Razorpay specific
    razorpay_order_id: Optional[str] = Field(index=True)
    razorpay_payment_id: Optional[str] = Field(index=True)
    razorpay_signature: Optional[str] = None
    
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: "User" = Relationship()
