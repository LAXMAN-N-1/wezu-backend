from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.battery_catalog import BatterySpec, BatteryBatch
    from app.models.rental import Rental
    from app.models.logistics import BatteryTransfer
from sqlmodel import SQLModel, Field, Relationship

# Import for relationships (Forward references stringified to avoid circular imports where possible)
class Battery(SQLModel, table=True):
    __tablename__ = "batteries"
    id: Optional[int] = Field(default=None, primary_key=True)
    serial_number: str = Field(index=True, unique=True)
    
    # Specs & Inventory (New)
    spec_id: Optional[int] = Field(default=None, foreign_key="battery_specs.id")
    batch_id: Optional[int] = Field(default=None, foreign_key="battery_batches.id")
    
    # State
    status: str = Field(default="new") # new, ready, rented, charging, maintenance, retired
    current_charge: float = Field(default=100.0)
    health_percentage: float = Field(default=100.0)
    cycle_count: int = Field(default=0)
    
    # Lifecycle Info
    purchase_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    retirement_date: Optional[datetime] = None
    last_maintenance_date: Optional[datetime] = None
    last_maintenance_cycles: int = Field(default=0)

    
    # Current Location Context
    # Polymorphic-like tracking: location_type enum ('warehouse', 'station', 'customer', 'transit')
    location_type: Optional[str] = None 
    location_id: Optional[int] = None 
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    spec: Optional["BatterySpec"] = Relationship(back_populates="batteries")
    batch: Optional["BatteryBatch"] = Relationship(back_populates="batteries")
    
    lifecycle_events: List["BatteryLifecycleEvent"] = Relationship(back_populates="battery")
    rentals: List["Rental"] = Relationship(back_populates="battery")
    iot_device: Optional["IoTDevice"] = Relationship(back_populates="battery")

class BatteryLifecycleEvent(SQLModel, table=True):
    __tablename__ = "battery_lifecycle_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    battery_id: int = Field(foreign_key="batteries.id")
    
    event_type: str = Field(index=True) # created, assigned, maintenance_start, maintenance_end, retired
    description: Optional[str] = None
    
    # Actor (who performed the action)
    actor_id: Optional[int] = None # AdminUser ID
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    battery: Battery = Relationship(back_populates="lifecycle_events")
