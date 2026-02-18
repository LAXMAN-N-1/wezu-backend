from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class LateFee(SQLModel, table=True):
    __tablename__ = "late_fees"
    __table_args__ = {"schema": "rentals"}
    """Late fee calculations for overdue rentals"""
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.rentals.id", unique=True)
    user_id: int = Field(foreign_key="core.users.id")
    
    original_end_date: datetime
    actual_return_date: Optional[datetime] = None
    days_overdue: int = Field(default=0)
    
    # Fee calculation
    daily_late_fee_rate: float
    base_late_fee: float = Field(default=0.0)
    
    # Progressive penalties (increases after certain days)
    progressive_penalty: float = Field(default=0.0)
    
    total_late_fee: float = Field(default=0.0)
    
    # Payment tracking
    amount_paid: float = Field(default=0.0)
    amount_waived: float = Field(default=0.0)
    amount_outstanding: float = Field(default=0.0)
    
    payment_status: str = Field(default="PENDING")  # PENDING, PARTIAL, PAID, WAIVED
    
    # Invoice generation
    invoice_id: Optional[int] = Field(default=None, foreign_key="finance.invoices.id")
    invoice_generated_at: Optional[datetime] = None
    
    # Waiver tracking
    waiver_request: Optional["LateFeeWaiver"] = Relationship(back_populates="late_fee")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    rental: "Rental" = Relationship()
    user: "User" = Relationship()

class LateFeeWaiver(SQLModel, table=True):
    __tablename__ = "late_fee_waivers"
    __table_args__ = {"schema": "rentals"}
    """Waiver requests for late fees"""
    id: Optional[int] = Field(default=None, primary_key=True)
    late_fee_id: int = Field(foreign_key="rentals.late_fees.id", unique=True)
    user_id: int = Field(foreign_key="core.users.id")
    
    requested_waiver_amount: float
    requested_waiver_percentage: Optional[float] = None  # e.g., 50% waiver
    
    reason: str
    supporting_documents: Optional[str] = None  # JSON array of document URLs
    
    status: str = Field(default="PENDING")  # PENDING, APPROVED, REJECTED, PARTIAL
    
    approved_waiver_amount: Optional[float] = None
    rejection_reason: Optional[str] = None
    
    reviewed_by: Optional[int] = Field(default=None, foreign_key="core.users.id")
    reviewed_at: Optional[datetime] = None
    
    admin_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    late_fee: LateFee = Relationship(back_populates="waiver_request")
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[LateFeeWaiver.user_id]"})
    reviewer: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[LateFeeWaiver.reviewed_by]"})
