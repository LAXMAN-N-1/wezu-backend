"""
Logistics-related Pydantic schemas
Delivery, driver, and route management models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Enums
class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class DriverStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ON_DELIVERY = "ON_DELIVERY"

class RouteStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class ReturnStatus(str, Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    PICKUP_SCHEDULED = "PICKUP_SCHEDULED"
    PICKED_UP = "PICKED_UP"
    INSPECTING = "INSPECTING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

# Request Models
class DriverOnboard(BaseModel):
    """Onboard new driver"""
    license_number: str = Field(..., min_length=10, max_length=20)
    license_expiry: datetime
    vehicle_type: str = Field(..., pattern=r'^(BIKE|SCOOTER|VAN|TRUCK)$')
    vehicle_plate: str = Field(..., min_length=6, max_length=15)
    vehicle_model: Optional[str] = None

class DriverStatusUpdate(BaseModel):
    """Update driver status"""
    is_online: bool

class LocationUpdate(BaseModel):
    """Update driver/delivery location"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = None

class DeliveryCreate(BaseModel):
    """Create delivery order"""
    order_id: int
    pickup_address: str
    delivery_address: str
    pickup_latitude: float
    pickup_longitude: float
    delivery_latitude: float
    delivery_longitude: float
    priority: Optional[str] = Field("NORMAL", pattern=r'^(LOW|NORMAL|HIGH|URGENT)$')
    scheduled_pickup: Optional[datetime] = None
    notes: Optional[str] = None

class DeliveryAssign(BaseModel):
    """Assign delivery to driver"""
    delivery_id: int
    driver_id: int

class DeliveryStatusUpdate(BaseModel):
    """Update delivery status"""
    status: DeliveryStatus
    notes: Optional[str] = None
    pod_image: Optional[str] = None  # Proof of delivery
    signature: Optional[str] = None
    recipient_name: Optional[str] = None

class RouteOptimizationRequest(BaseModel):
    """Request route optimization"""
    delivery_ids: List[int] = Field(..., min_items=2)
    start_location: Optional[dict] = None  # {lat, lng}
    optimization_type: str = Field("DISTANCE", pattern=r'^(DISTANCE|TIME|BALANCED)$')

class ReturnRequestCreate(BaseModel):
    """Create return request"""
    purchase_id: int
    reason: str = Field(..., pattern=r'^(DEFECTIVE|WRONG_ITEM|NOT_NEEDED|DAMAGED_IN_TRANSIT|OTHER)$')
    description: str = Field(..., min_length=10)
    images: Optional[List[str]] = None
    preferred_pickup_date: Optional[datetime] = None

class ReturnInspectionCreate(BaseModel):
    """Create return inspection"""
    return_request_id: int
    physical_condition: str = Field(..., pattern=r'^(EXCELLENT|GOOD|FAIR|POOR|DAMAGED)$')
    functional_status: str = Field(..., pattern=r'^(WORKING|NOT_WORKING|PARTIALLY_WORKING)$')
    packaging_intact: bool
    accessories_complete: bool
    deduction_amount: float = Field(0, ge=0)
    deduction_reason: Optional[str] = None
    inspector_notes: str
    inspection_images: Optional[List[str]] = None

# Response Models
class DriverProfileResponse(BaseModel):
    """Driver profile response"""
    id: int
    user_id: int
    license_number: str
    license_expiry: datetime
    vehicle_type: str
    vehicle_plate: str
    vehicle_model: Optional[str]
    is_online: bool
    current_latitude: Optional[float]
    current_longitude: Optional[float]
    rating: float
    total_deliveries: int
    created_at: datetime

    class Config:
        from_attributes = True

class DeliveryResponse(BaseModel):
    """Delivery assignment response"""
    id: int
    order_id: int
    driver_id: Optional[int]
    status: str
    pickup_address: str
    delivery_address: str
    priority: str
    scheduled_pickup: Optional[datetime]
    actual_pickup: Optional[datetime]
    estimated_delivery: Optional[datetime]
    actual_delivery: Optional[datetime]
    distance_km: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True

class DeliveryTrackingResponse(BaseModel):
    """Real-time delivery tracking"""
    delivery_id: int
    status: str
    driver_name: Optional[str]
    driver_phone: Optional[str]
    current_location: Optional[dict]  # {lat, lng}
    estimated_arrival: Optional[datetime]
    distance_remaining_km: Optional[float]
    route_polyline: Optional[str]

class RouteResponse(BaseModel):
    """Delivery route response"""
    id: int
    driver_id: int
    route_name: str
    status: str
    total_stops: int
    completed_stops: int
    total_distance_km: float
    estimated_duration_minutes: int
    actual_duration_minutes: Optional[int]
    optimized_path: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True

class RouteStopResponse(BaseModel):
    """Route stop response"""
    id: int
    route_id: int
    delivery_id: int
    stop_sequence: int
    stop_type: str
    address: str
    latitude: float
    longitude: float
    estimated_arrival: Optional[datetime]
    actual_arrival: Optional[datetime]
    status: str

    class Config:
        from_attributes = True

class ReturnRequestResponse(BaseModel):
    """Return request response"""
    id: int
    purchase_id: int
    user_id: int
    reason: str
    description: str
    status: str
    pickup_address: Optional[str]
    pickup_scheduled_at: Optional[datetime]
    refund_amount: Optional[float]
    refund_status: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReturnInspectionResponse(BaseModel):
    """Return inspection response"""
    id: int
    return_request_id: int
    inspector_id: int
    physical_condition: str
    functional_status: str
    packaging_intact: bool
    accessories_complete: bool
    approved_refund_amount: float
    deduction_amount: float
    deduction_reason: Optional[str]
    inspector_notes: str
    inspected_at: datetime

    class Config:
        from_attributes = True
