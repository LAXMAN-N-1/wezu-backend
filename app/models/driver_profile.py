from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.models.user import User

class DriverProfile(SQLModel, table=True):
    __tablename__ = "driver_profiles"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    
    license_number: str
    vehicle_type: str # e.g., e-bike, scooter, truck
    vehicle_plate: str
    
    is_online: bool = Field(default=False)
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    last_location_update: Optional[datetime] = None
    
    rating: float = Field(default=5.0)
    total_deliveries: int = Field(default=0)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship(back_populates="driver_profile")
