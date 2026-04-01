from typing import Optional
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field, Relationship
from app.models.driver_profile import DriverProfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.ecommerce import EcommerceOrder
    from app.models.return_request import ReturnRequest

class DeliveryAssignment(SQLModel, table=True):
    __tablename__ = "delivery_assignments"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Can be linked to an ecommerce order or a battery return
    order_id: Optional[int] = Field(default=None, foreign_key="ecommerce_orders.id")
    return_request_id: Optional[int] = Field(default=None, foreign_key="return_requests.id")
    
    driver_id: Optional[int] = Field(default=None, foreign_key="driver_profiles.id")
    status: str = Field(default="assigned") # assigned, picked_up, delivered, cancelled
    
    pickup_address: str
    delivery_address: str
    
    assigned_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(UTC))
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    proof_of_delivery_img: Optional[str] = None
    customer_signature: Optional[str] = None
    otp_verified: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    driver: Optional[DriverProfile] = Relationship()
    order: Optional["EcommerceOrder"] = Relationship(back_populates="delivery")
    return_request: Optional["ReturnRequest"] = Relationship(back_populates="delivery")
