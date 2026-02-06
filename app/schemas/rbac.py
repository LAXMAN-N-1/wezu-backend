from typing import List, Optional
from pydantic import BaseModel, ConfigDict

# Permission Schemas
class PermissionBase(BaseModel):
    slug: str
    module: str
    action: str
    description: Optional[str] = None
    scope: str = "all"

class PermissionCreate(PermissionBase):
    pass

class PermissionRead(PermissionBase):
    id: int
    
    
    model_config = ConfigDict(from_attributes=True)

# Permission Grouping Schemas
class PermissionItem(BaseModel):
    id: str # Mapped from slug
    label: str
    description: Optional[str] = None
    resource: str
    action: str
    scope: str = "all"

class PermissionModule(BaseModel):
    module: str
    label: str
    permissions: List[PermissionItem]

class PermissionListResponse(BaseModel):
    modules: List[PermissionModule]

class InheritedPermissions(BaseModel):
    source_role_id: int
    source_role_name: str
    permissions: List[PermissionItem]

class RolePermissionsResponse(BaseModel):
    direct_permissions: List[PermissionItem]
    inherited_permissions: List[InheritedPermissions]
    all_permissions_grouped: List[PermissionModule]

class RolePermissionAssign(BaseModel):
    permissions: List[str] # List of Permission Slugs
    mode: str = "overwrite" # "overwrite" | "append"

class RolePermissionUpdateResponse(BaseModel):
    users_affected: int
    role_id: int
    active_permissions: List[str] # Slugs

class PermissionCheckResponse(BaseModel):
    has_permission: bool
    granted_by_role: Optional[str] = None
    scope: Optional[str] = None
    conditions: Optional[dict] = None

# Role Schemas
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "system"
    level: int = 0


class RoleCreate(RoleBase):
    permissions: List[str] # List of Permission Slugs
    parent_role_id: Optional[int] = None


class RoleRead(RoleBase):
    id: int
    is_system_role: bool
    is_active: bool
    permissions: Optional[List[PermissionRead]] = None
    permission_count: int = 0
    category: str
    level: int
    parent_role_id: Optional[int] = None


    
    model_config = ConfigDict(from_attributes=True)

class RoleDetail(RoleRead):
    user_count: int = 0
    permission_tree: dict = {}
    parent_role: Optional["RoleRead"] = None
    child_roles: List["RoleRead"] = []

class RoleHierarchy(RoleRead):
    children: List["RoleHierarchy"] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    level: Optional[int] = None
    parent_role_id: Optional[int] = None
    permissions: Optional[List[str]] = None # List of Permission Slugs

class RoleDuplicate(BaseModel):
    new_name: str
    description: Optional[str] = None

from datetime import datetime

# User Assignment Schema
class UserRoleAssign(BaseModel):
    role_id: int
    effective_from: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None

class UserRoleAssignmentResponse(BaseModel):
    success: bool
    active_permissions: List[str]
    menu_config: List[dict]
