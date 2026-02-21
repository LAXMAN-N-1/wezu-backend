from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum

if TYPE_CHECKING:
    from app.models.logistics import DeliveryOrder

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
    __table_args__ = {"schema": "logistics"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="core.ecommerce_orders.id")
    user_id: int = Field(foreign_key="core.users.id")
    
    reason: str
    status: ReturnStatus = Field(default=ReturnStatus.PENDING)
    
    # Logistics Link
    delivery_order_id: Optional[int] = Field(default=None, foreign_key="logistics.delivery_orders.id")
    
    refund_amount: Optional[float] = None
    inspection_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    delivery_order: Optional["DeliveryOrder"] = Relationship(back_populates="return_request")
