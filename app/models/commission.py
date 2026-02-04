from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class CommissionConfig(SQLModel, table=True):
    __tablename__ = "commission_configs"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Target entity
    dealer_id: Optional[int] = Field(default=None, foreign_key="users.id")
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id")
    
    # Type of transaction
    transaction_type: str = Field(index=True) # rental, swap, purchase
    
    # Commission Rate
    percentage: float = Field(default=0.0)
    flat_fee: float = Field(default=0.0)
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CommissionLog(SQLModel, table=True):
    __tablename__ = "commission_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Reference to causing event
    transaction_id: int = Field(foreign_key="transactions.id")
    
    # Beneficiary
    dealer_id: Optional[int] = Field(default=None, foreign_key="users.id")
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id")
    
    # Earnings
    amount: float
    status: str = Field(default="pending") # pending, paid, reversed
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
