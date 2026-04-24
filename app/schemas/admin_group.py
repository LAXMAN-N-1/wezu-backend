from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class AdminGroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class AdminGroupCreate(AdminGroupBase):
    pass

class AdminGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class AdminGroupResponse(AdminGroupBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AdminGroupWithCount(AdminGroupResponse):
    member_count: int = 0
