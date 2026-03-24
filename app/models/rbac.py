from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.role_right import RoleRight
from datetime import datetime

# Link Table for Role <-> Permission
class RolePermission(SQLModel, table=True):
    __tablename__ = "role_permissions"
    # __table_args__ = {"schema": "public"}
    role_id: int = Field(foreign_key="roles.id", primary_key=True)
    permission_id: int = Field(foreign_key="permissions.id", primary_key=True)

# Link Table for AdminUser <-> Role
class AdminUserRole(SQLModel, table=True):
    __tablename__ = "admin_user_roles"
    # __table_args__ = {"schema": "public"}
    admin_id: int = Field(foreign_key="admin_users.id", primary_key=True)
    role_id: int = Field(foreign_key="roles.id", primary_key=True)
    
    assigned_by: Optional[int] = Field(default=None, foreign_key="admin_users.id")
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


# Link Table for User <-> Role (Many-to-Many)
class UserRole(SQLModel, table=True):
    __tablename__ = "user_roles"
    # __table_args__ = {"schema": "public"}
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    role_id: int = Field(foreign_key="roles.id", primary_key=True)
    
    assigned_by: Optional[int] = Field(default=None, foreign_key="admin_users.id")
    notes: Optional[str] = None
    effective_from: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Permission(SQLModel, table=True):
    __tablename__ = "permissions"
    # __table_args__ = {"schema": "public"}
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
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    category: str = Field(default="system") # powerfill_staff, vendor_staff, customer, system
    level: int = Field(default=0) # Hierarchy level (e.g. 100=Admin, 10=User)
    parent_id: Optional[int] = Field(default=None, foreign_key="roles.id")
    is_system_role: bool = Field(default=False)  # If True, cannot be deleted (e.g., Super Admin)
    is_active: bool = Field(default=True)
    
    # Hierarchy relationships
    parent: Optional["Role"] = Relationship(
        sa_relationship_kwargs={
            "remote_side": "Role.id",
            "primaryjoin": "Role.parent_id==Role.id",
            "back_populates": "children"
        }
    )
    children: List["Role"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "primaryjoin": "Role.parent_id==Role.id"
        }
    )

    permissions: List[Permission] = Relationship(back_populates="roles", link_model=RolePermission)
    
    admin_users: List["AdminUser"] = Relationship(
        back_populates="roles",
        link_model=AdminUserRole,
        sa_relationship_kwargs={
            "primaryjoin": "Role.id==AdminUserRole.role_id",
            "secondaryjoin": "AdminUser.id==AdminUserRole.admin_id"
        }
    )

    # Change to One-to-Many to match User model
    users: List["User"] = Relationship(back_populates="role")
    
    # Merged from app/models/role.py (Legacy/Chandu branch)
    role_rights: List["RoleRight"] = Relationship(back_populates="role", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

    @property
    def parent_role_id(self):
        return self.parent_id
    
    @parent_role_id.setter
    def parent_role_id(self, value):
        self.parent_id = value



# Data Scoping: Path Based Access
class UserAccessPath(SQLModel, table=True):
    __tablename__ = "user_access_paths"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Path Pattern e.g. "Asia/India/Telangana/%"
    path_pattern: str = Field(index=True)
    
    # Access Level
    access_level: str = Field(default="view") # view, manage, admin
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[int] = Field(default=None, foreign_key="admin_users.id")
    
    # Relationships
    user: "User" = Relationship(back_populates="access_paths")
