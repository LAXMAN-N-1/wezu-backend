from typing import Optional, List
from sqlmodel import SQLModel
from datetime import datetime

class RoleBase(SQLModel):
    name: str

class RoleCreate(RoleBase):
    pass

class RoleUpdate(SQLModel):
    name: Optional[str] = None

class RoleRead(RoleBase):
    id: int

    class Config:
        from_attributes = True
