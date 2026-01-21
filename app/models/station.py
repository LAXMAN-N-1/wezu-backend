from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Station(SQLModel, table=True):
    __tablename__ = "stations"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    address: str
    latitude: float
    longitude: float
    status: str = Field(default="active")
    contact_phone: Optional[str] = None
    opening_hours: Optional[str] = None # e.g. "09:00-22:00"
    rating: float = Field(default=0.0)
    total_reviews: int = Field(default=0)
    dealer_id: Optional[int] = Field(default=None, foreign_key="dealer_profiles.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    slots: List["Slot"] = Relationship(back_populates="station")
    reviews: List["Review"] = Relationship(back_populates="station")
    images: List["StationImage"] = Relationship(back_populates="station")
    dealer: Optional["DealerProfile"] = Relationship(back_populates="stations")

class StationImage(SQLModel, table=True):
    __tablename__ = "station_images"
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id")
    url: str
    is_primary: bool = Field(default=False)
    
    # Relationships
    station: Optional["Station"] = Relationship(back_populates="images")

class Slot(SQLModel, table=True):
    __tablename__ = "slots"
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id")
    slot_number: int
    status: str = Field(default="empty")
    battery_id: Optional[int] = Field(default=None, foreign_key="batteries.id")

    # Relationships
    station: Station = Relationship(back_populates="slots")
    battery: Optional["Battery"] = Relationship()
