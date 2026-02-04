from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Warehouse Schemas ---
class WarehouseBase(BaseModel):
    name: str
    address: Optional[str] = None
    city: str
    state: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    manager_id: Optional[int] = None
    is_active: bool = True

class WarehouseCreate(WarehouseBase):
    pass

class WarehouseResponse(WarehouseBase):
    id: int
    
    class Config:
        from_attributes = True

# --- Transfer Schemas ---
class BatteryTransferBase(BaseModel):
    battery_id: int
    to_location_type: str # warehouse, station
    to_location_id: int
    driver_id: Optional[int] = None
    vehicle_id: Optional[str] = None

class BatteryTransferCreate(BatteryTransferBase):
    from_location_type: str
    from_location_id: int

class BatteryTransferResponse(BatteryTransferBase):
    id: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
