from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

if TYPE_CHECKING:
    from app.models.station import Station

class StationHeartbeat(SQLModel, table=True):
    __tablename__ = "station_heartbeats"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id", index=True)
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    status: str = Field(default="online") # online, maintenance, error
    
    # Store metrics as a JSON string
    # Expected format: {"temperature": 45.5, "power_w": 1200, "latency_ms": 25}
    metrics: Optional[str] = None 
    
    # Relationships
    station: Optional["Station"] = Relationship()
