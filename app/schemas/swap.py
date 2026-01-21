"""
Battery swap-related Pydantic schemas
Swap requests, suggestions, and preferences
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Request Models
class SwapRequestCreate(BaseModel):
    """Create swap request"""
    rental_id: int
    station_id: int
    current_battery_soc: Optional[float] = Field(None, ge=0, le=100)
    reason: Optional[str] = None

class SwapExecute(BaseModel):
    """Execute battery swap"""
    station_id: int
    old_battery_serial: str = Field(..., min_length=5)
    new_battery_serial: str = Field(..., min_length=5)
    swap_fee: Optional[float] = Field(0, ge=0)

class SwapPreferenceUpdate(BaseModel):
    """Update user swap preferences"""
    prefer_nearby: int = Field(5, ge=1, le=10, description="Weight for nearby stations")
    prefer_fast_charging: int = Field(5, ge=1, le=10)
    prefer_high_rated: int = Field(5, ge=1, le=10)
    prefer_low_wait: int = Field(5, ge=1, le=10)
    max_acceptable_distance_km: float = Field(10.0, gt=0, le=50)
    favorite_station_ids: Optional[List[int]] = None
    blacklisted_station_ids: Optional[List[int]] = None
    notify_when_battery_below: int = Field(20, ge=5, le=50)
    notify_suggestion_radius_km: float = Field(5.0, gt=0, le=20)

class SwapSuggestionRequest(BaseModel):
    """Request swap suggestions"""
    rental_id: int
    current_latitude: float = Field(..., ge=-90, le=90)
    current_longitude: float = Field(..., ge=-180, le=180)
    current_battery_soc: float = Field(..., ge=0, le=100)
    max_distance_km: Optional[float] = Field(10, gt=0, le=50)

# Response Models
class SwapRequestResponse(BaseModel):
    """Swap request response"""
    id: int
    rental_id: int
    station_id: int
    status: str
    requested_at: datetime
    approved_at: Optional[datetime]
    completed_at: Optional[datetime]
    rejection_reason: Optional[str]

    class Config:
        from_attributes = True

class SwapHistoryResponse(BaseModel):
    """Swap history response"""
    id: int
    rental_id: int
    station_id: int
    old_battery_id: int
    new_battery_id: int
    old_battery_soc: float
    new_battery_soc: float
    swap_fee: float
    timestamp: datetime
    duration_seconds: Optional[int]

    class Config:
        from_attributes = True

class SwapSuggestionResponse(BaseModel):
    """Swap suggestion response"""
    id: int
    station_id: int
    station_name: str
    station_address: str
    distance_km: float
    estimated_travel_time_minutes: int
    station_availability_score: float
    station_rating: float
    estimated_wait_time_minutes: Optional[int]
    preference_match_score: float
    total_score: float
    priority_rank: int
    available_batteries: int
    fast_charging_available: bool

    class Config:
        from_attributes = True

class SwapPreferenceResponse(BaseModel):
    """Swap preference response"""
    id: int
    user_id: int
    prefer_nearby: int
    prefer_fast_charging: int
    prefer_high_rated: int
    prefer_low_wait: int
    max_acceptable_distance_km: float
    favorite_station_ids: Optional[List[int]]
    blacklisted_station_ids: Optional[List[int]]
    notify_when_battery_below: int
    notify_suggestion_radius_km: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StationAvailabilityResponse(BaseModel):
    """Station availability for swaps"""
    station_id: int
    station_name: str
    available_batteries: int
    total_capacity: int
    utilization_percentage: float
    average_wait_time_minutes: int
    fast_charging_slots: int
    operating_hours: dict
    is_open_now: bool
