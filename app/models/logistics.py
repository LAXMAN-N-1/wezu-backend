from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

class Warehouse(SQLModel, table=True):
    __tablename__ = "warehouses"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    address: Optional[str] = None
    city: str
    state: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    manager_id: Optional[int] = Field(default=None, foreign_key="users.id")
    is_active: bool = Field(default=True)
    
    # Relationships
    manager: Optional["User"] = Relationship()
    # inventory: List["Battery"] = Relationship() # Implied by battery.location_id

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
