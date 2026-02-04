from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

# Import Zone and Vendor for Relationship
from .location import Zone
from .vendor import Vendor
from .dealer import DealerProfile
from .battery import Battery

class Station(SQLModel, table=True):
    __tablename__ = "stations"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    
    # Location
    address: str
    latitude: float
    longitude: float
    zone_id: Optional[int] = Field(default=None, foreign_key="zones.id")
    
    # Ownership
    vendor_id: Optional[int] = Field(default=None, foreign_key="vendors.id")
    dealer_id: Optional[int] = Field(default=None, foreign_key="dealer_profiles.id")
    
    # Hardware Specs
    station_type: str = Field(default="automated") # automated, manual, hybrid
    power_type: str = Field(default="grid") # grid, solar, hybrid
    connectivity_type: str = Field(default="4g") # 4g, wifi, ethernet
    firmware_version: Optional[str] = None
    total_slots: int = Field(default=0)
    
    # Status
    status: str = Field(default="active")
    contact_phone: Optional[str] = None
    opening_hours: Optional[str] = None
    rating: float = Field(default=0.0)
    total_reviews: int = Field(default=0)
    last_maintenance_date: Optional[datetime] = None

    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    slots: List["StationSlot"] = Relationship(back_populates="station")
    images: List["StationImage"] = Relationship(back_populates="station")
    vendor: Optional["Vendor"] = Relationship()
    dealer: Optional["DealerProfile"] = Relationship(back_populates="stations")
    zone: Optional["Zone"] = Relationship(back_populates="stations")
    reviews: List["Review"] = Relationship(back_populates="station")

class StationImage(SQLModel, table=True):
    __tablename__ = "station_images"
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id")
    url: str
    is_primary: bool = Field(default=False)
    
    # Relationships
    station: Optional["Station"] = Relationship(back_populates="images")

class StationSlot(SQLModel, table=True):
    __tablename__ = "station_slots"
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id")
    
    slot_number: int
    status: str = Field(default="empty") # empty, charging, ready, maintenance, error
    is_locked: bool = Field(default=True)
    
    # Battery Connection
    battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id")
    
    # Real-time Telemetry Snapshot (for quick status access)
    current_power_w: float = Field(default=0.0)
    last_heartbeat: Optional[datetime] = None

    # Relationships
    station: Station = Relationship(back_populates="slots")
    battery: Optional["Battery"] = Relationship()
