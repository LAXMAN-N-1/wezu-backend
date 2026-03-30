from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
import uuid
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
    sku_id: Optional[int] = None
    
class BatteryCreate(BatteryBase):
    status: Optional[str] = "available"
    health_status: Optional[str] = "good"
    current_charge: float = 100.0
    health_percentage: float = 100.0
    location_type: Optional[str] = "warehouse"
    battery_type: Optional[str] = "48V/30Ah"
    manufacturer: Optional[str] = None
    manufacture_date: Optional[datetime] = None
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    notes: Optional[str] = None
    station_id: Optional[int] = None

class BatteryBulkCreate(BaseModel):
    items: List[BatteryCreate]

class BatteryUpdate(BaseModel):
    status: Optional[str] = None
    health_status: Optional[str] = None
    health_percentage: Optional[float] = None
    location_type: Optional[str] = None
    station_id: Optional[int] = None
    current_user_id: Optional[int] = None
    manufacturer: Optional[str] = None
    battery_type: Optional[str] = None
    notes: Optional[str] = None
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    last_inspected_at: Optional[datetime] = None
    description: Optional[str] = None # For lifecycle event/audit log

class BatteryResponse(BatteryBase):
    id: int
    status: str
    health_status: str
    current_charge: float
    health_percentage: float
    cycle_count: int
    total_cycles: int
    created_at: datetime
    updated_at: datetime
    
    # Tracking Info
    manufacturer: Optional[str] = None
    battery_type: Optional[str] = None
    location_type: str
    manufacture_date: Optional[datetime] = None
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    last_charged_at: Optional[datetime] = None
    last_inspected_at: Optional[datetime] = None
    notes: Optional[str] = None
    station_id: Optional[int] = None
    
    # Nested Info
    sku: Optional["BatterySpecResponse"] = None
    iot_device: Optional["IoTDeviceResponse"] = None
    
    model_config = ConfigDict(from_attributes=True)

class BatteryDetailResponse(BatteryResponse):
    lifecycle_events: List[BatteryLifecycleEventResponse] = []

class BatteryHealthReading(BaseModel):
    timestamp: datetime
    soh: float
    soc: float
    temperature: Optional[float] = None

class BatteryUtilizationResponse(BaseModel):
    total_batteries: int
    available_count: int
    rented_count: int
    maintenance_count: int
    retired_count: int
    utilization_percentage: float

class BatteryMaintenanceCreate(BaseModel):
    maintenance_type: str # preventive, corrective
    description: str
    cost: float = 0.0
    parts_replaced: Optional[str] = None

# --- Audit & History ---
class BatteryAuditLogResponse(BaseModel):
    id: int
    battery_id: int
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    timestamp: datetime
    changed_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class BatteryHealthHistoryResponse(BaseModel):
    id: int
    battery_id: int
    health_percentage: float
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BatteryListResponse(BaseModel):
    items: List[BatteryResponse]
    total_count: int

class BatteryBulkUpdateRequest(BaseModel):
    battery_ids: List[int]
    status: str
