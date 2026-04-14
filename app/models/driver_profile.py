from typing import Optional
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field, Relationship
from app.models.user import User

class DriverProfile(SQLModel, table=True):
    __tablename__ = "driver_profiles"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)

    name: Optional[str] = None
    phone_number: Optional[str] = None
    status: Optional[str] = Field(default="active")  # active, suspended, inactive

    license_number: str
    vehicle_type: str  # e.g., e-bike, scooter, truck
    vehicle_plate: str

    is_online: bool = Field(default=False)
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    current_battery_level: Optional[float] = None
    location_accuracy: Optional[float] = None
    last_location_update: Optional[datetime] = None
    
    rating: float = Field(default=5.0)
    total_deliveries: int = Field(default=0)
    on_time_deliveries: int = Field(default=0)
    total_delivery_time_seconds: int = Field(default=0)
    satisfaction_sum: float = Field(default=0.0)
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: User = Relationship(back_populates="driver_profile")
