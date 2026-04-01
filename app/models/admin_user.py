from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .rbac import Role
    from app.models.admin_group import AdminGroup
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field, Relationship

# Import link model for relationship
from .rbac import AdminUserRole

class AdminUser(SQLModel, table=True):
    __tablename__ = "admin_users"
    id: Optional[int] = Field(default=None, primary_key=True)
    phone_number: Optional[str] = Field(default=None, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    admin_group_id: Optional[int] = Field(default=None, foreign_key="admin_groups.id")

    # Relationships
    roles: List["Role"] = Relationship(
        back_populates="admin_users",
        link_model=AdminUserRole,
        sa_relationship_kwargs={
            "primaryjoin": "AdminUser.id==AdminUserRole.admin_id",
            "secondaryjoin": "Role.id==AdminUserRole.role_id"
        }
    )
    admin_group: Optional["AdminGroup"] = Relationship(back_populates="admin_users")
