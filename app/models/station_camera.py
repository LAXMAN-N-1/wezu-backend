from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.station import Station

class StationCamera(SQLModel, table=True):
    __tablename__ = "station_cameras"
    __table_args__ = {"schema": "stations"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.stations.id", index=True)
    
    name: str = Field(description="Name or location of the camera")
    rtsp_url: str = Field(description="The RTSP stream URL")
    status: str = Field(default="active", description="active, inactive, offline")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    station: Optional["Station"] = Relationship(back_populates="cameras")
