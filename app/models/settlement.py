from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.models.vendor import Vendor

class Settlement(SQLModel, table=True):
    __tablename__ = "settlements"
    __table_args__ = {"schema": "finance"}
    id: Optional[int] = Field(default=None, primary_key=True)
    vendor_id: Optional[int] = Field(default=None, foreign_key="finance.vendors.id")
    dealer_id: Optional[int] = Field(default=None, foreign_key="core.users.id")
    
    # Period
    start_date: datetime
    end_date: datetime
    
    # Financials
    total_revenue: float = Field(default=0.0) # Total collected from swaps
    platform_fee: float = Field(default=0.0) # Calculated commission
    tax_amount: float = Field(default=0.0) # GST/VAT if applicable
    payable_amount: float = Field(default=0.0) # Final amount to Vendor
    
    currency: str = Field(default="INR")
    status: str = Field(default="pending") # generated, approved, paid, failed
    
    transaction_reference: Optional[str] = None # Bank transfer ref
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    
    # Relationships
    vendor: Vendor = Relationship()
