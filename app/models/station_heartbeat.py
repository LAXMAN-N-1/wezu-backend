from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.station import Station

class StationHeartbeat(SQLModel, table=True):
    __tablename__ = "station_heartbeats"
    __table_args__ = {"schema": "stations"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.stations.id", index=True)
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    status: str = Field(default="online") # online, maintenance, error
    
    # Store metrics as a JSON string
    # Expected format: {"temperature": 45.5, "power_w": 1200, "latency_ms": 25}
    metrics: Optional[str] = None 
    
    # Relationships
    station: Optional["Station"] = Relationship()
