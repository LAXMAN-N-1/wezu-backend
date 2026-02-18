from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import uuid

if TYPE_CHECKING:
    from app.models.user import User

class DeliveryType(str, Enum):
    DEALER_RESTOCK = "dealer_restock"
    CUSTOMER_DELIVERY = "customer_delivery"
    REVERSE_LOGISTICS = "reverse_logistics"

class DeliveryStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"

class DeliveryOrder(SQLModel, table=True):
    __tablename__ = "delivery_orders"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Type & Status
    order_type: DeliveryType = Field(index=True)
    status: DeliveryStatus = Field(default=DeliveryStatus.PENDING, index=True)
    
    # Location
    origin_address: str
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    
    destination_address: str
    destination_lat: Optional[float] = None
    destination_lng: Optional[float] = None
    
    # Assignment
    assigned_driver_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Payload
    battery_ids_json: Optional[str] = None # List of battery IDs being moved
    
    # Timings
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Tracking
    tracking_url: Optional[str] = None
    proof_of_delivery_url: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    driver: Optional["User"] = Relationship(back_populates="delivery_orders")
