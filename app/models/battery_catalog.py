from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from app.models.battery import Battery

class BatteryCatalog(SQLModel, table=True):
    __tablename__ = "battery_catalog"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Product Info
    name: str = Field(index=True)
    brand: str
    model: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    
    # Specs
    capacity_mah: int
    voltage: float
    battery_type: str = Field(default="lithium_ion") # lithium_ion, lfp, nmc
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = None # "10x20x30 cm"
    
    # Commercial
    price_full_purchase: float = Field(default=0.0)
    price_per_day: float = Field(default=0.0)
    warranty_months: int = Field(default=0)
    
    # Meta
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_number: str = Field(unique=True, index=True)
    manufacturer: str
    production_date: datetime = Field(default_factory=datetime.utcnow)

