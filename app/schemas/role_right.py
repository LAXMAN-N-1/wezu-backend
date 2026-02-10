from typing import Optional
from sqlmodel import SQLModel
from datetime import datetime

class RoleRightBase(SQLModel):
    role_id: int
    menu_id: int
    can_view: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False

class RoleRightCreate(RoleRightBase):
    pass

class RoleRightUpdate(SQLModel):
    can_view: Optional[bool] = None
    can_create: Optional[bool] = None
    can_edit: Optional[bool] = None
    can_delete: Optional[bool] = None

class RoleRightRead(RoleRightBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
