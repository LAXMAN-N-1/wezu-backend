from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from app.models.admin_user import AdminUser

class AdminGroup(SQLModel, table=True):
    __tablename__ = "admin_groups"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationships
    admin_users: List["AdminUser"] = Relationship(back_populates="admin_group")
