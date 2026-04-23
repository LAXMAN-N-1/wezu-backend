from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, List
from datetime import datetime

class StationImageResponse(BaseModel):
    url: str
    is_primary: bool

class StationBase(BaseModel):
    name: str
    address: str
    city: Optional[str] = None
    latitude: float
    longitude: float
    status: str = "active"
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    is_24x7: bool = False
    amenities: Optional[str] = None
    
    # New Operational Fields
    station_type: str = "automated"
    total_slots: int = 0
    power_rating_kw: Optional[float] = None
    
    # Ownership/Location
    zone_id: Optional[int] = None
    dealer_id: Optional[int] = None

class StationCreate(StationBase):
    pass

class StationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None
    is_24x7: Optional[bool] = None
    amenities: Optional[str] = None
    total_slots: Optional[int] = None
    power_rating_kw: Optional[float] = None

class StationResponse(StationBase):
    id: int
    rating: float
    total_reviews: int
    available_batteries: int = 0
    available_slots: int = 0
    images: List[StationImageResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

class NearbyStationResponse(StationResponse):
    distance: float # km
    # available_batteries is already in StationResponse now

class StationPerformanceResponse(BaseModel):
    daily_rentals: int
    daily_revenue: float
    avg_duration_minutes: float
    satisfaction_score: float
    utilization_percentage: float

class StationMapResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    status: str
    available_batteries: int

class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    intensity: float # 0.0 to 1.0 based on demand

class NearbyFilterSchema(BaseModel):
    battery_type: Optional[str] = None
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    capacity_min: Optional[float] = None   # field name used by station_service
    capacity_max: Optional[float] = None
    charger_type: Optional[str] = None
    price_min: Optional[float] = None      # used by station_service for BatteryCatalog filter
    price_max: Optional[float] = None
    availability: bool = False             # if True, skip stations with 0 matching batteries

    @model_validator(mode="after")
    def validate_ranges(self):
        if (
            self.price_min is not None
            and self.price_max is not None
            and self.price_min > self.price_max
        ):
            raise ValueError("price_min cannot be greater than price_max")
        if (
            self.capacity_min is not None
            and self.capacity_max is not None
            and self.capacity_min > self.capacity_max
        ):
            raise ValueError("capacity_min cannot be greater than capacity_max")
        return self

class StationAvailabilityResponse(BaseModel):
    station_id: int
    available_count: int
    batteries: List[dict] # Use dict for now to avoid circular imports if any, or just Any

# --- Station Specs Schemas ---

class StationSpecsBase(BaseModel):
    total_slots: int
    station_type: str
    power_rating_kw: Optional[float] = None
    max_capacity: Optional[int] = None
    charger_type: Optional[str] = None
    temperature_control: bool = False
    safety_features: Optional[str] = None

class StationSpecsResponse(StationSpecsBase):
    station_id: int

class StationSpecsUpdate(BaseModel):
    total_slots: Optional[int] = None
    station_type: Optional[str] = None
    power_rating_kw: Optional[float] = None
    max_capacity: Optional[int] = None
    charger_type: Optional[str] = None
    temperature_control: Optional[bool] = None
    safety_features: Optional[str] = None
