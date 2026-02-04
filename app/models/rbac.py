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
    slug: str = Field(unique=True, index=True)  # e.g., "battery:view:all"
    module: str  # e.g., "battery", "station"
    resource_type: Optional[str] = None # e.g., "Battery", "StationSlot"
    action: str  # e.g., "view", "create", "delete"
    scope: str = Field(default="global") # global, regional, organizational, own
    constraints: Optional[str] = None # JSON string for action-level rules
    description: Optional[str] = None
    
    roles: List["Role"] = Relationship(back_populates="permissions", link_model=RolePermission)

class Role(SQLModel, table=True):
    __tablename__ = "roles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    category: str = Field(default="system") # system, vendor, staff
    level: int = Field(default=0) # Smaller is higher priority/authority
    
    parent_id: Optional[int] = Field(default=None, foreign_key="roles.id")
    is_system_role: bool = Field(default=False)
    
    # Hierarchy relationships
    parent: Optional["Role"] = Relationship(
        sa_relationship_kwargs={
            "remote_side": "Role.id",
            "back_populates": "children"
        }
    )
    children: List["Role"] = Relationship(back_populates="parent")

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


