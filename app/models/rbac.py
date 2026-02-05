from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

# Link Table for Role <-> Permission
class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"
    role_id: int = Field(foreign_key="roles.id", primary_key=True)
    permission_id: int = Field(foreign_key="permissions.id", primary_key=True)

# Link Table for AdminUser <-> Role
class AdminUserRole(SQLModel, table=True):
    __tablename__ = "admin_user_roles"
    admin_id: int = Field(foreign_key="admin_users.id", primary_key=True)
    role_id: int = Field(foreign_key="roles.id", primary_key=True)
    
    assigned_by: Optional[int] = Field(default=None, foreign_key="admin_users.id")
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


# Link Table for User <-> Role (Many-to-Many)
class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True)
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id", primary_key=True)

class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)  # e.g., "vendor:create"
    module: str  # e.g., "vendor", "finance"
    action: str  # e.g., "create", "read"
    description: Optional[str] = None
    
    roles: List["Role"] = Relationship(back_populates="permissions", link_model=RolePermission)

class Role(SQLModel, table=True):
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    category: str = Field(default="system") # powerfill_staff, vendor_staff, customer, system
    level: int = Field(default=0) # Hierarchy level (e.g. 100=Admin, 10=User)
    parent_role_id: Optional[int] = Field(default=None, foreign_key="roles.id")
    is_system_role: bool = Field(default=False)  # If True, cannot be deleted (e.g., Super Admin)
    
    permissions: List[Permission] = Relationship(back_populates="roles", link_model=RolePermission)
    
    admin_users: List["AdminUser"] = Relationship(
        back_populates="roles",
        link_model=AdminUserRole,
        sa_relationship_kwargs={
            "primaryjoin": "Role.id==AdminUserRole.role_id",
            "secondaryjoin": "AdminUser.id==AdminUserRole.admin_id"
        }
    )

    users: List["User"] = Relationship(back_populates="roles", link_model=UserRole)


