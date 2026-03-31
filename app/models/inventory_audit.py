import uuid
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class InventoryAuditLog(SQLModel, table=True):
    __tablename__ = "inventory_audit_logs"
    __table_args__ = {"schema": "inventory"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: Optional[uuid.UUID] = Field(foreign_key="inventory.batteries.id", index=True)
    
    action_type: str = Field(index=True) # transfer, manual_entry, disposal, status_change
    
    from_location_type: Optional[str] = None # warehouse, station, user
    from_location_id: Optional[int] = None
    
    to_location_type: Optional[str] = None
    to_location_id: Optional[int] = None
    
    actor_id: Optional[int] = Field(default=None, foreign_key="core.users.id")
    notes: Optional[str] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
