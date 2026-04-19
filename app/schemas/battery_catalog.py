from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

# --- Battery Spec Schemas ---
class BatterySpecBase(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    voltage: Optional[float] = None
    capacity_mah: Optional[float] = None
    weight_kg: Optional[float] = None
    dimensions: Optional[str] = None
    cycle_life_expectancy: Optional[int] = 1500

class BatterySpecCreate(BatterySpecBase):
    name: str
    brand: str
    voltage: float
    capacity_mah: float
    cycle_life_expectancy: int = 1500

class BatterySpecResponse(BatterySpecBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

# --- Battery Batch Schemas ---
class BatteryBatchBase(BaseModel):
    batch_number: str
    purchase_order_ref: Optional[str] = None
    quantity: int
    manufacturer_date: datetime

class BatteryBatchCreate(BatteryBatchBase):
    spec_id: int

class BatteryBatchResponse(BatteryBatchBase):
    id: int
    spec_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- Catalog Response ---
class BatteryCatalogResponse(BaseModel):
    specs: List[BatterySpecResponse]
    recent_batches: List[BatteryBatchResponse]
