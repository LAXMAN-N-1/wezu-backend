from datetime import datetime, UTC
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

class ReturnInspection(SQLModel, table=True):
    __tablename__ = "return_inspections"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    return_request_id: int = Field(foreign_key="return_requests.id", index=True)
    inspection_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    inspector_id: int = Field(foreign_key="users.id")
    condition: str
    notes: Optional[str] = None


if TYPE_CHECKING:
    from app.models.logistics import DeliveryOrder
    from app.models.delivery_assignment import DeliveryAssignment

class ReturnStatus(str, Enum):
    PENDING = "pending"
    PICKUP_ASSIGNED = "pickup_assigned"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    INSPECTED = "inspected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ReturnRequest(SQLModel, table=True):
    __tablename__ = "return_requests"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="ecommerce_orders.id")
    user_id: int = Field(foreign_key="users.id")
    
    reason: str
    status: ReturnStatus = Field(default=ReturnStatus.PENDING)
    
    # Logistics Link
    delivery_order_id: Optional[int] = Field(default=None, index=True)
    
    refund_amount: Optional[float] = None
    inspection_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    delivery_order: Optional["DeliveryOrder"] = Relationship(back_populates="return_request")
    delivery: Optional["DeliveryAssignment"] = Relationship(back_populates="return_request")
