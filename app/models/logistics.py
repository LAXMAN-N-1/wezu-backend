from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

# Warehouse moved to app/models/warehouse.py

class BatteryTransfer(SQLModel, table=True):
    __tablename__ = "battery_transfers"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    battery_id: int = Field(foreign_key="batteries.id")
    
    # Source
    from_location_type: str # warehouse, station
    from_location_id: int
    
    # Destination
    to_location_type: str
    to_location_id: int
    
    # Status
    status: str = Field(default="pending") # pending, in_transit, completed, cancelled
    
    # Logistics
    driver_id: Optional[int] = Field(default=None, foreign_key="users.id")
    vehicle_id: Optional[str] = None # License plate or ID
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Relationships
    battery: "Battery" = Relationship()
    driver: Optional["User"] = Relationship()
