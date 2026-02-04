from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

class ReturnRequest(SQLModel, table=True):
    __tablename__ = "return_requests"
    """Reverse logistics for purchased batteries"""
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="ecommerce_orders.id")
    user_id: int = Field(foreign_key="users.id")
    
    reason: str  # DEFECTIVE, WRONG_ITEM, NOT_NEEDED, DAMAGED_IN_TRANSIT
    detailed_reason: Optional[str] = None
    
    status: str = Field(default="REQUESTED")  
    # REQUESTED, APPROVED, REJECTED, PICKUP_SCHEDULED, PICKED_UP, 
    # INSPECTING, REFUND_INITIATED, COMPLETED, CANCELLED
    
    requested_items: dict = Field(sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))  # Array of {battery_id, quantity, reason}
    
    pickup_address: Optional[str] = None
    pickup_scheduled_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    
    refund_amount: Optional[float] = None
    refund_method: Optional[str] = None  # ORIGINAL_PAYMENT, WALLET, BANK_TRANSFER
    refund_initiated_at: Optional[datetime] = None
    refund_completed_at: Optional[datetime] = None
    
    admin_notes: Optional[str] = None
    approved_by: Optional[int] = Field(default=None, foreign_key="users.id")
    approved_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    order: "EcommerceOrder" = Relationship()
    user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[ReturnRequest.user_id]"})
    approver: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[ReturnRequest.approved_by]"})
    inspection: Optional["ReturnInspection"] = Relationship(back_populates="return_request")

class ReturnInspection(SQLModel, table=True):
    __tablename__ = "return_inspections"
    """Quality check on returned items"""
    id: Optional[int] = Field(default=None, primary_key=True)
    return_request_id: int = Field(foreign_key="return_requests.id", unique=True)
    
    inspector_id: int = Field(foreign_key="users.id")
    
    inspection_status: str  # PASSED, FAILED, PARTIAL
    
    # Detailed inspection results
    items_inspected: dict = Field(sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))  
    # Array of {battery_id, condition, defects, images, approved_for_refund}
    
    physical_condition: str  # EXCELLENT, GOOD, FAIR, POOR, DAMAGED
    functional_test_passed: bool = Field(default=False)
    
    approved_refund_amount: float
    deduction_amount: float = Field(default=0.0)
    deduction_reason: Optional[str] = None
    
    inspection_notes: Optional[str] = None
    inspection_images: Optional[list[str]] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    inspected_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    return_request: ReturnRequest = Relationship(back_populates="inspection")
    inspector: "User" = Relationship()
