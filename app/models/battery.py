from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from sqlalchemy import Column, JSON
from sqlmodel import Column as SQLColumn

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
    GOOD = "good"
    FAIR = "fair"
    CRITICAL = "critical"
    EXCELLENT = "excellent"
    POOR = "poor"
    DAMAGED = "damaged"


class Battery(SQLModel, table=True):
    __tablename__ = "batteries"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Identity
    serial_number: str = Field(index=True, unique=True)
    qr_code_data: Optional[str] = Field(default=None, unique=True, index=True)
    iot_device_id: Optional[str] = Field(default=None, index=True)
    
    # Product Catalog Link
    sku_id: Optional[int] = Field(default=None, foreign_key="inventory.battery_catalog.id")
    spec_id: Optional[int] = Field(default=None, foreign_key="inventory.battery_catalog.id")
    
    # Location tracking
    station_id: Optional[int] = Field(default=None, foreign_key="stations.stations.id", index=True)
    current_user_id: Optional[int] = Field(default=None, foreign_key="core.users.id", index=True)
    
    # Technical State
    status: BatteryStatus = Field(default=BatteryStatus.AVAILABLE, index=True)
    health_status: BatteryHealth = Field(default=BatteryHealth.GOOD)
    
    current_charge: float = Field(default=100.0)
    health_percentage: float = Field(default=100.0)
    cycle_count: int = Field(default=0)
    temperature_c: float = Field(default=25.0)
    
    # Lifecycle
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    last_maintenance_date: Optional[datetime] = None
    last_maintenance_cycles: int = Field(default=0)
    
    # Health Tracking (New)
    state_of_health: float = Field(default=100.0)
    health_status: BatteryHealth = Field(default=BatteryHealth.EXCELLENT) # EXCELLENT, GOOD, FAIR, POOR, DAMAGED
    temperature_history: List[float] = Field(default_factory=list, sa_column=Column(JSON))
    charge_cycles: int = Field(default=0) # Distinct from cycle_count for lifecycle tracking

    
    # Current Location Context
    # Polymorphic-like tracking: location_type enum ('warehouse', 'station', 'customer', 'transit')
    location_type: Optional[str] = None 
    location_id: Optional[int] = None 

    
    # Timestamps
    last_telemetry_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Location tracking
    warehouse_id: Optional[int] = Field(default=None, foreign_key="logistics.warehouses.id")

    # Relationships
    sku: Optional["BatteryCatalog"] = Relationship(back_populates="batteries")
    product: Optional["BatteryCatalog"] = Relationship(back_populates="batteries") # Alias for backward compat if needed
    spec: Optional["BatteryCatalog"] = Relationship(back_populates="batteries")
    rentals: List["Rental"] = Relationship(back_populates="battery")
    lifecycle_events: List["BatteryLifecycleEvent"] = Relationship(back_populates="battery")
    
    iot_device: Optional["IoTDevice"] = Relationship(
        back_populates="battery",
        sa_relationship_kwargs={"uselist": False}
    )
    
    # The station relationship is implicit via station_id, but cleaner to define if Station is imported
    # Defining it as generic object to avoid circular dep issues in file
    # station: Optional["Station"] = Relationship()

class BatteryLifecycleEvent(SQLModel, table=True):
    __tablename__ = "battery_lifecycle_events"
    __table_args__ = {"schema": "inventory"}
    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: int = Field(foreign_key="inventory.batteries.id")
    
    event_type: str = Field(index=True) # created, assigned, maintenance_start, maintenance_end, retired
    description: Optional[str] = None
    actor_id: Optional[int] = None # User ID
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    battery: Battery = Relationship(back_populates="lifecycle_events")
