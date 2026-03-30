from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, UUID4, ConfigDict
from app.models.stock_movement import StockTransactionType, StockMovementDirection

# Stock Schemas
class StockBase(BaseModel):
    warehouse_id: int
    product_id: int
    quantity_on_hand: int = 0
    quantity_available: int = 0
    quantity_reserved: int = 0
    quantity_damaged: int = 0
    quantity_in_transit: int = 0
    reorder_level: int = 10

class StockCreate(StockBase):
    pass

class StockUpdate(BaseModel):
    reorder_level: Optional[int] = None

class StockResponse(StockBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Stock Movement Schemas
class StockMovementBase(BaseModel):
    stock_id: int
    transaction_type: StockTransactionType
    quantity: int
    direction: StockMovementDirection
    reference_type: str
    reference_id: Optional[str] = None
    battery_ids: Optional[str] = None
    notes: Optional[str] = None

class StockMovementResponse(StockMovementBase):
    id: int
    created_at: datetime
    created_by: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)

# Operation Schemas
class StockReceiveRequest(BaseModel):
    warehouse_id: int
    product_id: int
    quantity: int
    reference_id: Optional[str] = None # e.g. PO Number
    notes: Optional[str] = None
    serial_numbers: Optional[List[str]] = None # Optional list of serial numbers for batteries

class StockAdjustmentRequest(BaseModel):
    warehouse_id: int
    product_id: int
    quantity: int # Positive value
    type: StockTransactionType # DAMAGED, ADJUSTMENT_ADD, ADJUSTMENT_SUB
    notes: Optional[str] = None

class StockTransferRequest(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    product_id: int
    quantity: int
    notes: Optional[str] = None
