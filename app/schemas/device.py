"""
Device and geofence schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# ── Device ───────────────────────────────────────────────

class DeviceCreate(BaseModel):
    user_id: int
    fcm_token: str
    device_type: str
    device_id: str
    device_name: Optional[str] = None

class DeviceResponse(BaseModel):
    id: int
    user_id: int
    fcm_token: str
    device_type: str
    device_id: str
    device_name: Optional[str] = None
    is_active: bool = True
    last_active_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Geofence ─────────────────────────────────────────────

class GeofenceCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_km: float
    alert_type: str = "entry"  # entry, exit, both

class GeofenceResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    radius_km: float
    alert_type: str
    is_active: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── GPS Tracking ─────────────────────────────────────────

class GPSTrackingLogResponse(BaseModel):
    id: int
    battery_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    latitude: float
    longitude: float
    speed: Optional[float] = None
    altitude: Optional[float] = None
    heading: Optional[float] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)
