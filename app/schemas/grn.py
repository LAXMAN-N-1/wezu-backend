from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.grn import GRNStatus

class GRNItemCreate(BaseModel):
    indent_item_id: int
    received_quantity: int = Field(..., ge=0)
    damaged_quantity: int = Field(default=0, ge=0)

class GRNCreate(BaseModel):
    notes: Optional[str] = None
    items: List[GRNItemCreate]

class GRNItemResponse(BaseModel):
    id: int
    grn_id: int
    indent_item_id: int
    product_id: int
    expected_quantity: int
    received_quantity: int
    damaged_quantity: int

    class Config:
        from_attributes = True

class GRNResponse(BaseModel):
    id: int
    indent_id: int
    dealer_id: int
    warehouse_id: int
    status: GRNStatus
    received_by: int
    notes: Optional[str] = None
    created_at: datetime
    items: List[GRNItemResponse]

    class Config:
        from_attributes = True
