from pydantic import BaseModel, ConfigDict
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
    
    model_config = ConfigDict(from_attributes=True)

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
    
    model_config = ConfigDict(from_attributes=True)
# --- Delivery Order (DeliveryAssignment) Schemas ---
class DeliveryOrderBase(BaseModel):
    order_type: str
    origin_address: str
    destination_address: str
    scheduled_at: Optional[datetime] = None
    battery_ids_json: Optional[str] = None

class DeliveryOrderCreate(DeliveryOrderBase):
    return_request_id: Optional[int] = None

class DeliveryOrderResponse(DeliveryOrderBase):
    id: int
    status: str
    assigned_driver_id: Optional[int] = None
    proof_of_delivery_url: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- Driver Profile Schemas ---
class DriverProfileBase(BaseModel):
    license_number: str
    vehicle_type: str
    vehicle_plate: str

class DriverProfileCreate(DriverProfileBase):
    user_id: int

class DriverProfileUpdate(BaseModel):
    license_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_plate: Optional[str] = None
    is_online: Optional[bool] = None

class DriverProfileResponse(DriverProfileBase):
    id: int
    user_id: int
    is_online: bool
    rating: float
    total_deliveries: int
    
    model_config = ConfigDict(from_attributes=True)

class DriverPerformanceResponse(BaseModel):
    driver_id: int
    on_time_rate: float
    avg_delivery_time_minutes: float
    satisfaction_score: float

# --- Route Optimization Schemas ---
class RouteStopRequest(BaseModel):
    delivery_assignment_id: int
    address: str
    latitude: float
    longitude: float

class RouteOptimizationRequest(BaseModel):
    driver_id: int
    stops: List[RouteStopRequest]

class RouteResponse(BaseModel):
    route_id: int
    optimized_stops: List[int] # Sequence of stop IDs or assignment IDs
    total_distance_km: float

# --- Reverse Logistics ---
class ReturnRequestCreate(BaseModel):
    order_id: int
    reason: str

class ReturnResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    reason: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
