from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

class DriverProfile(SQLModel, table=True):
    __tablename__ = "driver_profiles"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    
    license_number: str
    vehicle_type: str = Field(default="bike") # bike, van, truck
    vehicle_plate: str
    
    is_online: bool = Field(default=False)
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    last_location_update: Optional[datetime] = None
    
    rating: float = Field(default=5.0)
    total_deliveries: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: "User" = Relationship(back_populates="driver_profile")
    assignments: List["DeliveryAssignment"] = Relationship(back_populates="driver")

class DeliveryAssignment(SQLModel, table=True):
    __tablename__ = "delivery_assignments"
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: Optional[int] = Field(default=None, foreign_key="ecommerce_orders.id") # Link to EcommerceOrder
    return_request_id: Optional[int] = Field(default=None) # Link to Return (if implemented)
    
    driver_id: Optional[int] = Field(default=None, foreign_key="driver_profiles.id")
    
    # Status: PENDING, ASSIGNED, PICKED_UP, IN_TRANSIT, DELIVERED, FAILED
    status: str = Field(default="PENDING")
    
    pickup_address: str # Can be station address or warehouse
    delivery_address: str # User address
    
    assigned_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    proof_of_delivery_img: Optional[str] = None
    customer_signature: Optional[str] = None
    otp_verified: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    driver: Optional[DriverProfile] = Relationship(back_populates="assignments")
    order: Optional["EcommerceOrder"] = Relationship(back_populates="delivery")
