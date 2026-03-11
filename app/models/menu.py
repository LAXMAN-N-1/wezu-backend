from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Menu(SQLModel, table=True):
    __tablename__ = "menus"
    __table_args__ = {"schema": "core"}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False)
    display_name: str = Field(nullable=False)
    route: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[int] = Field(default=None, foreign_key="core.menus.id")
    menu_order: int = Field(default=0)
    is_active: bool = Field(default=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    modified_by: Optional[str] = None

    # Self-referential relationship for parent-child hierarchy
    parent: Optional["Menu"] = Relationship(
        back_populates="children", 
        sa_relationship_kwargs={"remote_side": "Menu.id"}
    )
    children: List["Menu"] = Relationship(back_populates="parent")
    
    # Relationship with role rights
    role_rights: List["RoleRight"] = Relationship(back_populates="menu", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
