from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
import uuid

if TYPE_CHECKING:
    from app.models.battery import Battery
    from app.models.user import User


# --- Enums ---

class SnapshotType(str, Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    IOT_SYNC = "iot_sync"

class MaintenanceType(str, Enum):
    INSPECTION = "inspection"
    DEEP_SERVICE = "deep_service"
    REPLACEMENT = "replacement"
    CALIBRATION = "calibration"

class MaintenancePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class MaintenanceStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"

class AlertType(str, Enum):
    CRITICAL_HEALTH = "critical_health"
    RAPID_DEGRADATION = "rapid_degradation"
    HIGH_TEMP = "high_temp"
    OVERDUE_SERVICE = "overdue_service"
    WARRANTY_EXPIRY = "warranty_expiry"

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# --- Models ---

class BatteryHealthSnapshot(SQLModel, table=True):
    __tablename__ = "battery_health_snapshots"
    __table_args__ = {"schema": "inventory"}

    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: uuid.UUID = Field(foreign_key="inventory.batteries.id", index=True)

    health_percentage: float  # 0-100
    voltage: Optional[float] = None  # e.g. 51.4V
    temperature: Optional[float] = None  # e.g. 38.5°C
    internal_resistance: Optional[float] = None  # e.g. 15mΩ
    charge_cycles: Optional[int] = None

    snapshot_type: SnapshotType = Field(default=SnapshotType.MANUAL)
    recorded_by: Optional[int] = Field(default=None, foreign_key="core.users.id")
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class BatteryMaintenanceSchedule(SQLModel, table=True):
    __tablename__ = "battery_maintenance_schedules"
    __table_args__ = {"schema": "inventory"}

    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: uuid.UUID = Field(foreign_key="inventory.batteries.id", index=True)

    scheduled_date: datetime
    maintenance_type: MaintenanceType
    priority: MaintenancePriority = Field(default=MaintenancePriority.MEDIUM)
    assigned_to: Optional[int] = Field(default=None, foreign_key="core.users.id")
    status: MaintenanceStatus = Field(default=MaintenanceStatus.SCHEDULED, index=True)
    notes: Optional[str] = None

    # Health readings at completion
    health_before: Optional[float] = None
    health_after: Optional[float] = None

    completed_at: Optional[datetime] = None
    created_by: Optional[int] = Field(default=None, foreign_key="core.users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BatteryHealthAlert(SQLModel, table=True):
    __tablename__ = "battery_health_alerts"
    __table_args__ = {"schema": "inventory"}

    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: uuid.UUID = Field(foreign_key="inventory.batteries.id", index=True)

    alert_type: AlertType
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING)
    message: str

    is_resolved: bool = Field(default=False, index=True)
    resolved_by: Optional[int] = Field(default=None, foreign_key="core.users.id")
    resolved_at: Optional[datetime] = None
    resolution_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
