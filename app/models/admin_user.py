from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .rbac import Role
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

# Import link model for relationship
from .rbac import AdminUserRole

class AdminUser(SQLModel, table=True):
    __tablename__ = "admin_users"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    phone_number: Optional[str] = Field(default=None, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    roles: List["Role"] = Relationship(
        back_populates="admin_users",
        link_model=AdminUserRole,
        sa_relationship_kwargs={
            "primaryjoin": "AdminUser.id==AdminUserRole.admin_id",
            "secondaryjoin": "Role.id==AdminUserRole.role_id"
        }
    )
