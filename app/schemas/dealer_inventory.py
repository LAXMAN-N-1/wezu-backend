"""
Dealer Inventory schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class DealerInventoryResponse(BaseModel):
    id: int
    dealer_id: int
    battery_model: str
    quantity_available: int = 0
    quantity_reserved: int = 0
    quantity_damaged: int = 0
    reorder_level: int = 0
    max_capacity: int = 0
    last_restocked_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class DealerInventoryAdjust(BaseModel):
    battery_model: str
    adjustment_quantity: int
    reason: str
    reference_number: Optional[str] = None

class InventoryTransactionResponse(BaseModel):
    id: int
    dealer_inventory_id: int
    transaction_type: str
    quantity: int
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    performed_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DealerInventoryListResponse(BaseModel):
    items: List[DealerInventoryResponse]
    total_count: int
