from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint, Column, Numeric
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.driver_profile import DriverProfile

class Order(SQLModel, table=True):
    __tablename__ = "logistics_orders"
    
    id: str = Field(primary_key=True)  # ORD-XXXXXX
    # Statuses: pending, in_transit, delivered, failed, cancelled
    status: str = Field(default="pending")
    priority: str = Field(default="normal")  # urgent, normal, low
    units: int = Field(default=1)
    destination: str
    
    # Geospatial fields
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    notes: Optional[str] = None
    customer_name: str = Field(default="Walk-in Customer")
    customer_phone: Optional[str] = None
    total_value: Decimal = Field(default=Decimal("0.0"), sa_column=Column(Numeric(12, 2)))
    tracking_number: Optional[str] = None
    # Denormalized JSON mirror for API compatibility. Source of truth is logistics_order_batteries.
    assigned_battery_ids: Optional[str] = None
    assigned_driver_id: Optional[int] = Field(default=None, foreign_key="driver_profiles.id")
    
    # Timestamps
    order_date: datetime = Field(default_factory=datetime.utcnow)
    estimated_delivery: Optional[datetime] = None
    dispatch_date: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Proof of Delivery
    proof_of_delivery_url: Optional[str] = None
    proof_of_delivery_notes: Optional[str] = None
    proof_of_delivery_captured_at: Optional[datetime] = None
    proof_of_delivery_signature_url: Optional[str] = None
    recipient_name: Optional[str] = None
    
    # Failure info
    failure_reason: Optional[str] = None

    # Scheduling & Communication
    scheduled_slot_start: Optional[datetime] = None
    scheduled_slot_end: Optional[datetime] = None
    is_confirmed: bool = Field(default=False)
    confirmation_sent_at: Optional[datetime] = None
    
    # Return & Reverse Logistics
    type: str = Field(default="delivery")  # delivery, return
    original_order_id: Optional[str] = Field(default=None) # Start with simple string to avoid recursive import issues
    refund_status: str = Field(default="none")  # none, pending, processed, failed

    # Relationships
    driver: Optional["DriverProfile"] = Relationship()


class OrderBattery(SQLModel, table=True):
    __tablename__ = "logistics_order_batteries"
    __table_args__ = (
        UniqueConstraint("order_id", "battery_id", name="uq_logistics_order_battery"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: str = Field(foreign_key="logistics_orders.id", index=True)
    battery_id: str = Field(index=True)
    battery_pk: Optional[int] = Field(default=None, foreign_key="batteries.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
