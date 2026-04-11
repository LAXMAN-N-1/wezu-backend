from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC

class Telemetry(SQLModel, table=True):
    __tablename__ = "telemetry"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Source
    device_id: str = Field(index=True) # IoT Device ID
    battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id", index=True)
    rental_id: Optional[int] = Field(default=None, foreign_key="rentals.id")
    
    # Data
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kmph: Optional[float] = None
    
    voltage: Optional[float] = None
    current: Optional[float] = None
    temperature: Optional[float] = None
    soc: Optional[float] = None # State of Charge
    soh: Optional[float] = None # State of Health
    
    range_remaining_km: Optional[float] = None
    
    # Timestamp (Indexed for time-series queries)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    
    # Metadata
    metadata_json: Optional[str] = None
