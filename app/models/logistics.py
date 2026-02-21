from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING, List
from datetime import datetime
from enum import Enum
import uuid

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.return_request import ReturnRequest

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

class BatteryTransfer(SQLModel, table=True):
    __tablename__ = "battery_transfers"
    __table_args__ = {"schema": "logistics"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: int = Field(foreign_key="inventory.batteries.id")
    
    from_location_type: str # warehouse, station, dealer
    from_location_id: int
    
    to_location_type: str
    to_location_id: int
    
    status: str = Field(default="pending") # pending, assigned, in_transit, received, cancelled
    manifest_id: Optional[int] = Field(default=None, foreign_key="logistics.manifests.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    manifest: Optional["Manifest"] = Relationship(back_populates="transfers")

class Manifest(SQLModel, table=True):
    __tablename__ = "manifests"
    __table_args__ = {"schema": "logistics"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    manifest_number: str = Field(default_factory=lambda: f"MAN-{uuid.uuid4().hex[:8].upper()}", index=True, unique=True)
    
    driver_id: Optional[int] = Field(default=None, foreign_key="core.users.id")
    vehicle_id: Optional[str] = None
    
    status: str = Field(default="draft") # draft, assigned, active, closed
    
    transfers: List[BatteryTransfer] = Relationship(back_populates="manifest")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Update Relationship for User
if TYPE_CHECKING:
    from app.models.user import User
    
class DeliveryOrder(SQLModel, table=True):
    __tablename__ = "delivery_orders"
    __table_args__ = {"schema": "logistics"}
    
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
    assigned_driver_id: Optional[int] = Field(default=None, foreign_key="core.users.id")
    
    # Payload
    battery_ids_json: Optional[str] = None # List of battery IDs being moved
    
    # Timings
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Tracking
    tracking_url: Optional[str] = None
    proof_of_delivery_url: Optional[str] = None
    customer_signature_url: Optional[str] = None
    otp_verified: bool = Field(default=False)
    completion_otp: Optional[str] = None
    
    # Reverse Logistics Link
    return_request_id: Optional[int] = Field(default=None, foreign_key="logistics.return_requests.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    driver: Optional["User"] = Relationship(back_populates="delivery_orders")
    return_request: Optional["ReturnRequest"] = Relationship(back_populates="delivery_order")

