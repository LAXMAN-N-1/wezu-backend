from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.indent import IndentStatus

class IndentItemCreate(BaseModel):
    product_id: int
    requested_quantity: int = Field(..., ge=1)

class IndentCreate(BaseModel):
    warehouse_id: int
    notes: Optional[str] = None
    items: List[IndentItemCreate]

class IndentItemResponse(BaseModel):
    id: int
    product_id: int
    requested_quantity: int
    approved_quantity: int
    dispatched_quantity: int
    received_quantity: int

    class Config:
        from_attributes = True

class IndentResponse(BaseModel):
    id: int
    dealer_id: int
    warehouse_id: int
    status: IndentStatus
    notes: Optional[str] = None
    manager_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[IndentItemResponse]

    class Config:
        from_attributes = True

class IndentApproveItem(BaseModel):
    item_id: int
    approved_quantity: int = Field(..., ge=0)

class IndentApproveRequest(BaseModel):
    manager_notes: Optional[str] = None
    items: List[IndentApproveItem]
