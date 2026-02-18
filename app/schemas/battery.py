from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.battery_catalog import BatterySpecResponse, BatteryBatchResponse
from app.schemas.iot import IoTDeviceResponse

# --- Lifecycle Event Schemas ---
class BatteryLifecycleEventBase(BaseModel):
    event_type: str
    description: Optional[str] = None

class BatteryLifecycleEventCreate(BatteryLifecycleEventBase):
    battery_id: int
    actor_id: Optional[int] = None

class BatteryLifecycleEventResponse(BatteryLifecycleEventBase):
    id: int
    timestamp: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- Battery Schemas ---
class BatteryBase(BaseModel):
    serial_number: str
    spec_id: Optional[int] = None
    batch_id: Optional[int] = None
    
    # Deprecated fields (gradual migration)
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    capacity_ah: Optional[float] = None
    nominal_voltage: float = 60.0
    
class BatteryCreate(BatteryBase):
    pass

class BatteryBulkCreate(BaseModel):
    items: List[BatteryCreate]

class BatteryUpdate(BaseModel):
    status: Optional[str] = None
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    description: Optional[str] = None # For lifecycle event

class BatteryResponse(BatteryBase):
    id: int
    status: Optional[str] = "new"
    current_charge: Optional[float] = 0.0
    health_percentage: Optional[float] = 100.0
    cycle_count: Optional[int] = 0
    created_at: datetime
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    
    # Nested Info
    spec: Optional["BatterySpecResponse"] = None
    batch: Optional["BatteryBatchResponse"] = None
    iot_device: Optional["IoTDeviceResponse"] = None
    
    model_config = ConfigDict(from_attributes=True)

class BatteryDetailResponse(BatteryResponse):
    lifecycle_events: List[BatteryLifecycleEventResponse] = []
