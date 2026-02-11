"""
Maintenance-related Pydantic schemas
Maintenance schedules, records, and station downtime
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# Request Models
class MaintenanceScheduleCreate(BaseModel):
    """Create maintenance schedule"""
    battery_id: int
    maintenance_type: str = Field(..., pattern=r'^(ROUTINE|INSPECTION|REPAIR|REPLACEMENT)$')
    scheduled_date: datetime
    assigned_technician_id: Optional[int] = None
    priority: str = Field("NORMAL", pattern=r'^(LOW|NORMAL|HIGH|URGENT)$')
    estimated_duration_minutes: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = None

class MaintenanceRecordCreate(BaseModel):
    """Create maintenance record"""
    battery_id: int
    maintenance_type: str = Field(..., pattern=r'^(ROUTINE|INSPECTION|REPAIR|REPLACEMENT|EMERGENCY)$')
    performed_by: int
    issues_found: Optional[str] = None
    actions_taken: str = Field(..., min_length=10)
    parts_replaced: Optional[List[str]] = None
    cost: Optional[float] = Field(None, ge=0)
    next_maintenance_date: Optional[datetime] = None
    battery_health_after: Optional[float] = Field(None, ge=0, le=100)

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
    battery_id: int
    battery_serial: Optional[str]
    maintenance_type: str
    scheduled_date: datetime
    assigned_technician_id: Optional[int]
    technician_name: Optional[str]
    priority: str
    status: str
    estimated_duration_minutes: Optional[int]
    notes: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MaintenanceRecordResponse(BaseModel):
    """Maintenance record response"""
    id: int
    battery_id: int
    battery_serial: Optional[str]
    maintenance_type: str
    performed_by: int
    technician_name: Optional[str]
    performed_at: datetime
    issues_found: Optional[str]
    actions_taken: str
    parts_replaced: Optional[List[str]]
    cost: Optional[float]
    duration_minutes: Optional[int]
    next_maintenance_date: Optional[datetime]
    battery_health_before: Optional[float]
    battery_health_after: Optional[float]

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


