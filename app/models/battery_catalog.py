from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

class BatterySpec(SQLModel, table=True):
    __tablename__ = "battery_specs"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True) # e.g. "60V Li-ion Type A"
    manufacturer: str
    voltage: float
    capacity_ah: float
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = None # LxWxH
    cycle_life_expectancy: int = 1500
    
    # Relationships
    batches: List["BatteryBatch"] = Relationship(back_populates="spec")
    batteries: List["Battery"] = Relationship(back_populates="spec")

class BatteryBatch(SQLModel, table=True):
    __tablename__ = "battery_batches"
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_number: str = Field(index=True, unique=True)
    spec_id: int = Field(foreign_key="battery_specs.id")
    
    manufacturer_date: datetime
    purchase_order_ref: Optional[str] = None
    quantity: int
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    spec: BatterySpec = Relationship(back_populates="batches")
    batteries: List["Battery"] = Relationship(back_populates="batch")
