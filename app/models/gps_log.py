from __future__ import annotations
"""
GPS Tracking Log Model
Stores location history for active rentals
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone; UTC = timezone.utc

class GPSTrackingLog(SQLModel, table=True):
    """GPS location tracking for rentals"""
    __tablename__ = "gps_tracking_log"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_id: int = Field(foreign_key="rentals.id", index=True)
    battery_id: int = Field(foreign_key="batteries.id", index=True)
    
    # Location data
    latitude: float = Field(index=True)
    longitude: float = Field(index=True)
    accuracy: Optional[float] = None  # GPS accuracy in meters
    altitude: Optional[float] = None
    speed: Optional[float] = None  # Speed in km/h
    heading: Optional[float] = None  # Direction in degrees
    
    # Timestamp
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    
    # Metadata
    provider: Optional[str] = None  # GPS, NETWORK, FUSED
    is_mock_location: bool = Field(default=False)
