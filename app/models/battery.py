from datetime import datetime, UTC
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from sqlalchemy import Column, JSON
from sqlmodel import Column as SQLColumn
import uuid

if TYPE_CHECKING:
    from app.models.battery_catalog import BatteryCatalog, BatterySpec, BatteryBatch
    from app.models.rental import Rental
    from app.models.station import Station, StationSlot
    from app.models.iot import IoTDevice
    from app.models.logistics import BatteryTransfer

class BatteryStatus(str, Enum):
    AVAILABLE = "available"
    RENTED = "rented"
    MAINTENANCE = "maintenance"
    CHARGING = "charging"
    RETIRED = "retired"

class BatteryHealth(str, Enum):
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    CRITICAL = "CRITICAL"
    EXCELLENT = "EXCELLENT"
    DAMAGED = "DAMAGED"


class LocationType(str, Enum):
    STATION = "station"
    WAREHOUSE = "warehouse"
    SERVICE_CENTER = "service_center"
    RECYCLING = "recycling"

class Battery(SQLModel, table=True):
    __tablename__ = "batteries"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Identity
    serial_number: str = Field(index=True, unique=True)
    qr_code_data: Optional[str] = Field(default=None, unique=True, index=True)
    iot_device_id: Optional[str] = Field(default=None, index=True)
    
    # Product Catalog Link
    sku_id: Optional[int] = Field(default=None, foreign_key="battery_catalog.id")
    spec_id: Optional[int] = Field(default=None, foreign_key="battery_catalog.id")
    
    # Location tracking
    station_id: Optional[int] = Field(default=None, foreign_key="stations.id", index=True)
    current_user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Technical State
    status: BatteryStatus = Field(default=BatteryStatus.AVAILABLE, index=True)
    health_status: BatteryHealth = Field(default=BatteryHealth.GOOD)
    
    current_charge: float = Field(default=100.0)
    health_percentage: float = Field(default=100.0)
    cycle_count: int = Field(default=0)
    total_cycles: int = Field(default=0)
    temperature_c: float = Field(default=25.0)
    
    # New Battery Management Fields
    manufacturer: Optional[str] = Field(default=None)
    battery_type: Optional[str] = Field(default="48V/30Ah")
    purchase_cost: float = Field(default=0.0)
    notes: Optional[str] = Field(default=None)
    location_type: LocationType = Field(default=LocationType.WAREHOUSE)
    
    # Lifecycle
    manufacture_date: Optional[datetime] = None
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    last_charged_at: Optional[datetime] = None
    last_inspected_at: Optional[datetime] = None
    last_maintenance_date: Optional[datetime] = None
    last_maintenance_cycles: int = Field(default=0)
    
    # Health Tracking (New)
    state_of_health: float = Field(default=100.0)
    temperature_history: List[float] = Field(default_factory=list, sa_column=Column(JSON))
    charge_cycles: int = Field(default=0) # Distinct from cycle_count for lifecycle tracking

    
    # Current Location Context
    # Polymorphic-like tracking: location_type enum ('warehouse', 'station', 'customer', 'transit')
    location_id: Optional[int] = None 

    
    # Timestamps
    last_telemetry_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)}
    )

    # Relationships
    sku: Optional["BatteryCatalog"] = Relationship(
        back_populates="batteries",
        sa_relationship_kwargs={"foreign_keys": "[Battery.sku_id]"}
    )
    product: Optional["BatteryCatalog"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Battery.sku_id]",
            "overlaps": "sku"
        }
    )
    rentals: List["Rental"] = Relationship(back_populates="battery")
    lifecycle_events: List["BatteryLifecycleEvent"] = Relationship(back_populates="battery")
    
    iot_device: Optional["IoTDevice"] = Relationship(
        back_populates="battery",
        sa_relationship_kwargs={"uselist": False}
    )

class BatteryLifecycleEvent(SQLModel, table=True):
    __tablename__ = "battery_lifecycle_events"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: int = Field(foreign_key="batteries.id")
    
    event_type: str = Field(index=True) # created, assigned, maintenance_start, maintenance_end, retired
    description: Optional[str] = None
    actor_id: Optional[int] = None # User ID
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    battery: Battery = Relationship(back_populates="lifecycle_events")

class BatteryAuditLog(SQLModel, table=True):
    __tablename__ = "battery_audit_logs"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: int = Field(foreign_key="batteries.id", index=True)
    
    changed_by: Optional[int] = Field(default=None, foreign_key="users.id")
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

class BatteryHealthHistory(SQLModel, table=True):
    __tablename__ = "battery_health_history"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: int = Field(foreign_key="batteries.id", index=True)
    
    health_percentage: float
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
