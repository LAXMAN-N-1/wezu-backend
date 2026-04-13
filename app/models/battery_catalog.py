from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, UTC
import uuid

if TYPE_CHECKING:
    from app.models.battery import Battery

class BatteryCatalog(SQLModel, table=True):
    __tablename__ = "battery_catalog"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Product Info
    name: str = Field(index=True)
    brand: Optional[str] = None
    model: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    
    # Specs
    capacity_mah: Optional[int] = None
    capacity_ah: Optional[float] = None
    cycle_life_expectancy: Optional[int] = None
    voltage: float
    battery_type: str = Field(default="lithium_ion", index=True) # lithium_ion, lfp, nmc
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = None # "10x20x30 cm"
    
    # Commercial
    price_full_purchase: float = Field(default=0.0)
    price_per_day: float = Field(default=0.0, index=True)
    warranty_months: int = Field(default=0)
    
    # Meta
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationships
    batteries: List["Battery"] = Relationship(
        back_populates="sku",
        sa_relationship_kwargs={
            "foreign_keys": "[Battery.sku_id]",
            "overlaps": "product"
        }
    )

BatterySpec = BatteryCatalog

class BatteryBatch(SQLModel, table=True):
    __tablename__ = "battery_batches"
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_number: str = Field(unique=True, index=True)
    manufacturer: str
    production_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
