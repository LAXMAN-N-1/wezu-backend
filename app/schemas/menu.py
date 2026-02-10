from typing import Optional, List
from sqlmodel import SQLModel
from datetime import datetime

class MenuBase(SQLModel):
    name: str
    display_name: str
    route: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    menu_order: int = 0
    is_active: bool = True

class MenuCreate(MenuBase):
    pass

class MenuUpdate(SQLModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    route: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = None
    menu_order: Optional[int] = None
    is_active: Optional[bool] = None

class MenuRead(MenuBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MenuReadWithChildren(MenuRead):
    children: List["MenuReadWithChildren"] = []
