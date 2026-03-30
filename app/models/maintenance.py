from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC

class MaintenanceSchedule(SQLModel, table=True):
    __tablename__ = "maintenance_schedules"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str # battery, station
    model_name: Optional[str] = None # e.g. "Lithium-X1" or "Station-V2"
    model_config = {"protected_namespaces": ()}
    
    interval_days: Optional[int] = None
    interval_cycles: Optional[int] = None # For batteries
    
    last_maintenance_date: Optional[datetime] = None
    next_maintenance_date: Optional[datetime] = None # For batteries
    
    checklist: str # JSON list of items
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class MaintenanceRecord(SQLModel, table=True):
    __tablename__ = "maintenance_records"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str # battery, station
    entity_id: int # ID of battery or station
    
    technician_id: int = Field(foreign_key="users.id")
    
    maintenance_type: str # preventive, corrective
    description: str
    cost: float = Field(default=0.0)
    parts_replaced: Optional[str] = None # JSON
    
    status: str = Field(default="completed")
    performed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    technician: "User" = Relationship()

class StationDowntime(SQLModel, table=True):
    __tablename__ = "station_downtimes"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.id")
    
    start_time: datetime
    end_time: Optional[datetime] = None
    reason: str
    
    station: "Station" = Relationship()
