from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from typing import Optional
from datetime import datetime

class RoleRight(SQLModel, table=True):
    __tablename__ = "role_rights"

    id: Optional[int] = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="core.roles.id", nullable=False)
    menu_id: int = Field(foreign_key="core.menus.id", nullable=False)
    
    can_view: bool = Field(default=False)
    can_create: bool = Field(default=False)
    can_edit: bool = Field(default=False)
    can_delete: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    modified_by: Optional[str] = None

    # Relationships
    role: "Role" = Relationship(back_populates="role_rights")
    menu: "Menu" = Relationship(back_populates="role_rights")

    __table_args__ = (
        UniqueConstraint("role_id", "menu_id", name="unique_role_menu"),
        {"schema": "core"}
    )
