from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
import uuid


# --- Overview ---

class HealthOverviewResponse(BaseModel):
    fleet_avg_health: float
    good_count: int  # > 80%
    fair_count: int  # 50-80%
    poor_count: int  # 30-50%
    critical_count: int  # < 30%
    avg_degradation_rate: float  # %/month
    batteries_needing_service: int
    scheduled_maintenance_count: int
    total_batteries: int


# --- Battery List ---

class HealthBatteryResponse(BaseModel):
    id: str  # UUID as string
    serial_number: str
    manufacturer: Optional[str] = None
    battery_type: Optional[str] = None
    status: str
    health_percentage: float
    health_status: str  # good/fair/poor/critical

    # Latest snapshot data
    voltage: Optional[float] = None
    temperature: Optional[float] = None
    internal_resistance: Optional[float] = None
    charge_cycles: Optional[int] = None

    degradation_rate: float  # %/month
    last_reading_at: Optional[str] = None
    last_maintenance_at: Optional[str] = None
    days_since_maintenance: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# --- Battery Detail ---

class HealthSnapshotResponse(BaseModel):
    id: int
    health_percentage: float
    voltage: Optional[float] = None
    temperature: Optional[float] = None
    internal_resistance: Optional[float] = None
    charge_cycles: Optional[int] = None
    snapshot_type: str
    recorded_at: str

    model_config = ConfigDict(from_attributes=True)


class MaintenanceScheduleResponse(BaseModel):
    id: int
    battery_id: str
    battery_serial: Optional[str] = None
    scheduled_date: str
    maintenance_type: str
    priority: str
    assigned_to: Optional[int] = None
    assigned_to_name: Optional[str] = None
    status: str
    notes: Optional[str] = None
    health_before: Optional[float] = None
    health_after: Optional[float] = None
    completed_at: Optional[str] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class HealthAlertResponse(BaseModel):
    id: int
    battery_id: str
    battery_serial: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    is_resolved: bool
    resolved_by: Optional[int] = None
    resolved_at: Optional[str] = None
    resolution_reason: Optional[str] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class HealthBatteryDetailResponse(BaseModel):
    id: str
    serial_number: str
    manufacturer: Optional[str] = None
    battery_type: Optional[str] = None
    status: str
    health_percentage: float
    health_status: str

    # Telemetry
    voltage: Optional[float] = None
    temperature: Optional[float] = None
    internal_resistance: Optional[float] = None
    charge_cycles: Optional[int] = None
    total_cycles: int = 0
    cycle_count: int = 0

    # Computed
    degradation_rate: float
    predicted_eol_date: Optional[str] = None
    predicted_fair_date: Optional[str] = None
    estimated_remaining_cycles: Optional[int] = None
    estimated_remaining_years: Optional[float] = None

    # Health breakdown
    voltage_health: float = 100.0
    temperature_health: float = 100.0
    resistance_health: float = 100.0
    cycle_health: float = 100.0

    # History
    snapshots: List[HealthSnapshotResponse] = []
    maintenance_history: List[MaintenanceScheduleResponse] = []
    active_alerts: List[HealthAlertResponse] = []

    # Stats
    min_health: Optional[float] = None
    max_health: Optional[float] = None
    avg_health: Optional[float] = None
    fastest_drop: Optional[float] = None
    fastest_drop_week: Optional[str] = None

    warranty_expiry: Optional[str] = None
    last_maintenance_at: Optional[str] = None
    created_at: Optional[str] = None


# --- Create Schemas ---

class HealthSnapshotCreate(BaseModel):
    health_percentage: float
    voltage: Optional[float] = None
    temperature: Optional[float] = None
    internal_resistance: Optional[float] = None
    notes: Optional[str] = None


class MaintenanceScheduleCreate(BaseModel):
    battery_id: str
    scheduled_date: str
    maintenance_type: str  # inspection / deep_service / calibration / replacement
    priority: str = "medium"
    assigned_to: Optional[int] = None
    notes: Optional[str] = None


class AlertResolveRequest(BaseModel):
    reason: str


# --- Analytics ---

class FleetHealthTrendPoint(BaseModel):
    date: str
    avg_health: float

class WorstDegrader(BaseModel):
    battery_id: str
    serial_number: str
    degradation_rate: float
    current_health: float

class HealthAnalyticsResponse(BaseModel):
    fleet_trend: List[FleetHealthTrendPoint]
    health_distribution: dict  # {"good": 15, "fair": 7, "poor": 2, "critical": 1}
    worst_degraders: List[WorstDegrader]
    maintenance_compliance_rate: float  # % of scheduled maintenance completed on time
