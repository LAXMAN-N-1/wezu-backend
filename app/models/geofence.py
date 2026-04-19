from __future__ import annotations
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, timezone; UTC = timezone.utc

class Geofence(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    latitude: float
    longitude: float
    radius_meters: float = Field(default=1000.0)
    
    type: str = Field(default="safe_zone") # safe_zone, restricted_zone, station_perimeter
    polygon_coords: Optional[str] = None # JSON string of [[lat,lng],...]
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
