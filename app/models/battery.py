from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Battery(SQLModel, table=True):
    __tablename__ = "batteries"
    id: Optional[int] = Field(default=None, primary_key=True)
    serial_number: str = Field(index=True, unique=True)
    model: str
    capacity_ah: float
    current_charge: float = Field(default=100.0)
    status: str = Field(default="available")
    
    # Health Metrics
    health_percentage: float = Field(default=100.0)
    cycle_count: int = Field(default=0)
    temperature: float = Field(default=25.0) # Celsius
    voltage: float = Field(default=0.0)
    
    # Info
    warranty_expiry: Optional[datetime] = None
    purchase_date: Optional[datetime] = None
    
    last_swap_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    rentals: List["Rental"] = Relationship(back_populates="battery")
    purchases: List["Purchase"] = Relationship(back_populates="battery")
    iot_device: Optional["IoTDevice"] = Relationship(back_populates="battery")
