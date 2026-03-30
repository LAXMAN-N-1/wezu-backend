from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class WarehouseBase(BaseModel):
    name: str
    code: str
    address: str
    city: str
    state: str
    pincode: str
    branch_id: Optional[int] = None
    manager_id: Optional[int] = None
    is_active: bool = True

class WarehouseCreate(WarehouseBase):
    pass

class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    branch_id: Optional[int] = None
    manager_id: Optional[int] = None
    is_active: Optional[bool] = None

class WarehouseRead(WarehouseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
