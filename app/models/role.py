from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Role(SQLModel, table=True):
    __tablename__ = "roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, nullable=False)
    
    users: List["User"] = Relationship(back_populates="role")
    role_rights: List["RoleRight"] = Relationship(back_populates="role", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
