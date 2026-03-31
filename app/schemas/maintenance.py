"""
Maintenance-related Pydantic schemas
Maintenance schedules, records, and station downtime
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict
from datetime import datetime

# Maintenance Templates
class MaintenanceTemplateBase(BaseModel):
    name: str
    station_type: Optional[str] = None
    entity_type: Optional[str] = Field("station", pattern=r'^(battery|station)$')
    maintenance_type: Optional[str] = None
    description: Optional[str] = None
    checklist: List[str] # List of items
    version: int = 1
    is_active: bool = True

class MaintenanceTemplateCreate(MaintenanceTemplateBase):
    pass

class MaintenanceTemplateUpdate(BaseModel):
    name: Optional[str] = None
    entity_type: Optional[str] = None
    description: Optional[str] = None
    checklist: Optional[List[Dict]] = None
    is_active: Optional[bool] = None

class MaintenanceTemplateResponse(MaintenanceTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Request Models
class MaintenanceScheduleCreate(BaseModel):
    """Create maintenance schedule"""
    station_id: int
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_minutes: Optional[int] = None
    maintenance_type: str = "preventive"
    status: str = "scheduled"
    recurrence_rule: Optional[str] = None
    assigned_to: Optional[int] = None

class MaintenanceScheduleUpdate(BaseModel):
    """Update maintenance schedule"""
    station_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    maintenance_type: Optional[str] = None
    status: Optional[str] = None
    recurrence_rule: Optional[str] = None
    assigned_to: Optional[int] = None

class MaintenanceRecordCreate(BaseModel):
    """Create maintenance record"""
    schedule_id: Optional[int] = None
    station_id: Optional[int] = None
   # performed_by: int
    status: str = "completed"
    checklist_result: Optional[Dict[str, bool]] = None
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Legacy fields
    battery_id: Optional[int] = None
    entity_type: Optional[str] = Field("station", pattern=r'^(battery|station)$')
    #entity_id: Optional[int] = None
    template_id: Optional[int] = None
    maintenance_type: str = Field("preventive", pattern=r'^(ROUTINE|INSPECTION|REPAIR|REPLACEMENT|EMERGENCY|preventive)$')
    issues_found: Optional[str] = None
    actions_taken: Optional[str] = None
    parts_replaced: Optional[List[str]] = None
    #checklist_submission: Optional[List[Dict]] = None # Filled checklist
    #cost: Optional[float] = Field(None, ge=0)
    next_maintenance_date: Optional[datetime] = None
    #battery_health_after: Optional[float] = None

class StationDowntimeCreate(BaseModel):
    """Report station downtime"""
    station_id: int
    reason: str = Field(..., pattern=r'^(MAINTENANCE|POWER_OUTAGE|EQUIPMENT_FAILURE|NETWORK_ISSUE|OTHER)$')
    description: str = Field(..., min_length=10)
    severity: str = Field(..., pattern=r'^(LOW|MEDIUM|HIGH|CRITICAL)$')
    estimated_resolution_time: Optional[datetime] = None
    affected_slots: Optional[int] = None

class StationDowntimeUpdate(BaseModel):
    """Update station downtime"""
    status: str = Field(..., pattern=r'^(ONGOING|RESOLVED|ESCALATED)$')
    resolution_notes: Optional[str] = None
    actual_resolution_time: Optional[datetime] = None

class BatteryHealthCheckRequest(BaseModel):
    """Request battery health check"""
    battery_ids: List[int] = Field(..., min_items=1)
    check_type: str = Field("STANDARD", pattern=r'^(QUICK|STANDARD|COMPREHENSIVE)$')

# Response Models
class MaintenanceScheduleResponse(BaseModel):
    """Maintenance schedule response"""
    id: int
    station_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    maintenance_type: Optional[str] = None
    status: str
    recurrence_rule: Optional[str] = None
    assigned_to: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class CalendarViewResponse(BaseModel):
    """Calendar view response"""
    id: int
    station_id: Optional[int] = None
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str
    assigned_to: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

class MaintenanceRecordResponse(BaseModel):
    """Maintenance record response"""
    id: int
    schedule_id: Optional[int] = None
    station_id: Optional[int] = None
   # performed_by: int
    status: str
    checklist_result: Optional[Dict[str, bool]] = None
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Legacy fields
    entity_type: Optional[str] = None
   # entity_id: Optional[int] = None
    battery_id: Optional[int] = None
    template_id: Optional[int] = None
    template_name: Optional[str] = None
    maintenance_type: Optional[str] = None
    technician_name: Optional[str] = None
    performed_at: datetime
    issues_found: Optional[str] = None
    actions_taken: Optional[str] = None
    parts_replaced: Optional[List[str]] = None
    #checklist_submission: Optional[List[Dict]] = None
    #cost: Optional[float] = None
    duration_minutes: Optional[int] = None
    next_maintenance_date: Optional[datetime] = None
   # battery_health_before: Optional[float] = None
    #battery_health_after: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class StationDowntimeResponse(BaseModel):
    """Station downtime response"""
    id: int
    station_id: int
    station_name: Optional[str]
    reason: str
    description: str
    severity: str
    status: str
    started_at: datetime
    estimated_resolution_time: Optional[datetime]
    actual_resolution_time: Optional[datetime]
    duration_minutes: Optional[int]
    affected_slots: Optional[int]
    resolution_notes: Optional[str]
    reported_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)

class BatteryHealthSummaryResponse(BaseModel):
    """Battery health summary"""
    battery_id: int
    battery_serial: str
    current_health_percentage: float
    last_maintenance_date: Optional[datetime]
    next_maintenance_due: Optional[datetime]
    total_maintenance_count: int
    average_soc: float
    cycle_count: int
    issues_detected: List[str]
    maintenance_cost_total: float
    status: str

class MaintenanceDashboardResponse(BaseModel):
    """Maintenance dashboard statistics"""
    batteries_due_maintenance: int
    scheduled_maintenance_today: int
    overdue_maintenance: int
    active_downtimes: int
    average_battery_health: float
    total_maintenance_cost_month: float
    top_issues: List[Dict]
    technician_workload: Dict

class MaintenanceHistoryResponse(BaseModel):
    """Maintenance history for a battery"""
    battery_id: int
    battery_serial: str
    total_maintenance_count: int
    total_cost: float
    average_health_trend: List[Dict]  # [{date, health_percentage}]
    maintenance_records: List[MaintenanceRecordResponse]
    upcoming_schedules: List[MaintenanceScheduleResponse]


class OverdueAlertResponse(BaseModel):
    """Alert response for overdue scheduled tasks"""
    id: int
    station_id: int
    title: str
    scheduled_time: datetime
    status: str
    delay_minutes: int
