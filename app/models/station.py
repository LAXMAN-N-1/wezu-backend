import uuid
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum


if TYPE_CHECKING:
    from app.models.dealer import DealerProfile
    from app.models.vendor import Vendor
    from app.models.battery import Battery
    from app.models.location import Zone
    from app.models.review import Review
    from app.models.geofence import Geofence

class StationStatus(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    MAINTENANCE = "MAINTENANCE"
    CLOSED = "CLOSED"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"

class Station(SQLModel, table=True):
    __tablename__ = "stations"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    tenant_id: Optional[str] = Field(default="default", index=True)

    # Location
    address: str
    city: Optional[str] = None
    latitude: float = Field(index=True)
    longitude: float = Field(index=True)
    zone_id: Optional[int] = Field(default=None, foreign_key="zones.id")
    
    # Ownership
    owner_id: Optional[int] = Field(default=None, foreign_key="users.id") # Dealer/Owner
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id") # Assuming vendor is in finance or core? I'll check.
    dealer_id: Optional[int] = Field(default=None, foreign_key="dealer_profiles.id")
    
    # Hardware Specs
    station_type: str = Field(default="automated") # automated, manual, hybrid
    total_slots: int = Field(default=0)
    power_rating_kw: Optional[float] = None
    max_capacity: Optional[int] = Field(default=None)
    charger_type: Optional[str] = Field(default=None)
    temperature_control: bool = Field(default=False)
    safety_features: Optional[str] = None
    
    # Inventory
    available_batteries: int = Field(default=0)
    available_slots: int = Field(default=0)
    

    # Structured charger configuration  (JSON array)
    # [{"type": "CCS2", "count": 4, "power_kw": 50, "efficiency": 0.95, "speed": "fast"}]
    charger_configs: Optional[str] = Field(default=None)

    # Operating temperature range (°C)
    operating_temp_min: Optional[float] = Field(default=None)
    operating_temp_max: Optional[float] = Field(default=None)

    # Auto-close rental config
    auto_close_enabled: bool = Field(default=False)
    auto_close_grace_minutes: int = Field(default=30)

    # Status
    status: str = Field(default="active")
    approval_status: str = Field(default="approved") # pending, approved, rejected
    contact_phone: Optional[str] = None
    operating_hours: Optional[str] = None # Legacy plain string
    # Structured day-by-day hours (JSON)
    # {"mon": {"open": "09:00", "close": "18:00"}, ..., "holidays": {"open": null, "close": null}}
    structured_hours: Optional[str] = Field(default=None)
    is_24x7: bool = Field(default=False)
    amenities: Optional[str] = None # JSON string
    image_url: Optional[str] = None
    
    # Ratings
    rating: float = Field(default=0.0)
    total_reviews: int = Field(default=0)
    last_maintenance_date: Optional[datetime] = None
    
    # Inventory settings
    low_stock_threshold_pct: float = Field(default=20.0)

    # Geofence linkage
    geofence_id: Optional[int] = Field(default=None, foreign_key="geofence.id")

    
    # Timestamps
    last_heartbeat: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    slots: List["StationSlot"] = Relationship(back_populates="station")
    images: List["StationImage"] = Relationship(back_populates="station")
    
    zone: Optional["Zone"] = Relationship(back_populates="stations")
    dealer: Optional["DealerProfile"] = Relationship(back_populates="stations")
    reviews: List["Review"] = Relationship(back_populates="station")
    geofence: Optional["Geofence"] = Relationship(back_populates="station")
    
    # Foreign Key Relationships
    # Note: Circular imports are handled by string forward references in many cases, 
    # but explicit imports closer to top are preferred if no circularity.
    # We will assume DealerProfile/Vendor/Zone are defined elsewhere correctly.

class StationImage(SQLModel, table=True):
    __tablename__ = "station_images"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id")
    url: str
    is_primary: bool = Field(default=False)
    
    station: Optional["Station"] = Relationship(back_populates="images")

class StationSlot(SQLModel, table=True):
    __tablename__ = "station_slots"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id")
    
    slot_number: int
    status: str = Field(default="empty") # empty, charging, ready, maintenance, error
    is_locked: bool = Field(default=True)
    
    # Battery Connection
    battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id")
    
    # Real-time Telemetry
    current_power_w: float = Field(default=0.0)
    last_heartbeat: Optional[datetime] = None

    # Relationships
    station: Station = Relationship(back_populates="slots")
