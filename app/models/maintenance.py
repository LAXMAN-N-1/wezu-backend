from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.station import Station

class MaintenanceTemplate(SQLModel, table=True):
    __tablename__ = "maintenance_templates"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    station_type: Optional[str] = None
    entity_type: str # battery, station
    maintenance_type: Optional[str] = None
    description: Optional[str] = None
    checklist: str # JSON list of items/questions
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class MaintenanceSchedule(SQLModel, table=True):
    __tablename__ = "maintenance_schedules"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # New Fields for explicit calendar tasks
    station_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    maintenance_type: Optional[str] = None
    status: str = Field(default="scheduled")
    recurrence_rule: Optional[str] = None
    assigned_to: Optional[int] = Field(default=None, foreign_key="core.users.id")
    
    # Legacy Fields for rule generation
    entity_type: Optional[str] = None # battery, station
    model_name: Optional[str] = None # e.g. "Lithium-X1" or "Station-V2"
    model_config = {"protected_namespaces": ()}
    
    interval_days: Optional[int] = None
    interval_cycles: Optional[int] = None # For batteries
    
    last_maintenance_date: Optional[datetime] = None
    next_maintenance_date: Optional[datetime] = None # For batteries
    
    checklist: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    assigned_user: Optional["User"] = Relationship()

class MaintenanceRecord(SQLModel, table=True):
    __tablename__ = "maintenance_records"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_id: Optional[int] = Field(default=None, foreign_key="inventory.maintenance_schedules.id")
    entity_type: Optional[str] = None # battery, station
    entity_id: Optional[int] = None # ID of battery or station
    station_id: Optional[int] = None # Direct associate
    
    technician_id: int = Field(foreign_key="core.users.id")
    template_id: Optional[int] = Field(default=None, foreign_key="inventory.maintenance_templates.id")
    
    maintenance_type: Optional[str] = None # preventive, corrective
    description: Optional[str] = None
    cost: float = Field(default=0.0)
    parts_replaced: Optional[str] = None # JSON
    checklist_submission: Optional[str] = None # old checklist style, JSON
    checklist_result: Optional[str] = None # New checklist format (key-value bools), JSON
    notes: Optional[str] = None
    
    status: str = Field(default="completed")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    performed_at: datetime = Field(default_factory=datetime.utcnow)
    
    technician: "User" = Relationship()
    template: Optional[MaintenanceTemplate] = Relationship()

class StationDowntime(SQLModel, table=True):
    __tablename__ = "station_downtimes"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    station_id: int = Field(foreign_key="stations.stations.id")
    
    start_time: datetime
    end_time: Optional[datetime] = None
    reason: str
    
    station: "Station" = Relationship()
