import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class BatteryHealthLog(SQLModel, table=True):
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: Optional[uuid.UUID] = Field(foreign_key="inventory.batteries.id")
    
    charge_percentage: float
    voltage: float
    current: float
    temperature: float
    cycle_count: int
    health_percentage: float
    current_capacity_mah: Optional[float] = None # For SOH calculation
    
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Relationship
    battery: "Battery" = Relationship()
