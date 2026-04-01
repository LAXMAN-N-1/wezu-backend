from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

if TYPE_CHECKING:
    from app.models.station import Station

class Alert(SQLModel, table=True):
    __tablename__ = "alerts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: Optional[int] = Field(default=None, foreign_key="stations.id", index=True)
    
    # OFFLINE | PERFORMANCE | HARDWARE | OVERHEAT | TAMPERING | POWER_FAIL
    alert_type: str = Field(index=True) 
    # LOW | MEDIUM | HIGH | CRITICAL
    severity: str = Field(default="MEDIUM") 
    message: str
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Relationships
    station: Optional["Station"] = Relationship()
