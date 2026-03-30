from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

# ----- Permission Schemas -----

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

class PermissionItem(BaseModel):
    id: str
    label: str
    description: Optional[str] = None
    resource: str
    action: str
    scope: str = "all"

class PermissionModule(BaseModel):
    module: str
    label: str
    permissions: List[PermissionItem] = []

class PermissionListResponse(BaseModel):
    modules: List[PermissionModule] = []

# ----- Role Schemas -----

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "system"
    level: int = 0
    is_active: bool = True

class RoleCreate(RoleBase):
    permissions: List[str] = []
    permission_ids: List[int] = []
    parent_role_id: Optional[int] = Field(default=None, alias="parent_id")

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    level: Optional[int] = None
    is_active: Optional[bool] = None
    permissions: Optional[List[str]] = None
    parent_role_id: Optional[int] = Field(default=None, alias="parent_id")

class PermissionResponse(BaseModel):
    id: int
    slug: str
    module: str
    action: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class RoleRead(RoleBase):
    id: int
    parent_role_id: Optional[int] = None
    permissions: Optional[List[PermissionResponse]] = []
    permission_count: Optional[int] = 0
    model_config = ConfigDict(from_attributes=True)

RoleResponse = RoleRead

class RoleDetail(RoleRead):
    user_count: Optional[int] = 0
    permission_tree: Dict[str, List[str]] = {}
    parent_role: Optional["RoleRead"] = None
    child_roles: List["RoleRead"] = []


class RoleHierarchy(RoleRead):
    children: List["RoleHierarchy"] = []
    permission_count: int = 0
    model_config = ConfigDict(from_attributes=True)

# ----- Role Permissions -----

class InheritedPermissions(BaseModel):
    source_role_id: int
    source_role_name: str
    permissions: List[PermissionItem]

class RolePermissionsResponse(BaseModel):
    direct_permissions: List[PermissionItem]
    inherited_permissions: List[InheritedPermissions] = []
    all_permissions_grouped: List[PermissionModule] = []

class RolePermissionAssign(BaseModel):
    permissions: List[str]
    mode: str = "overwrite"  # overwrite | append

class RolePermissionUpdateResponse(BaseModel):
    role_id: int
    users_affected: int = 0
    active_permissions: List[str] = []

# ----- User Role assignment -----

class UserRoleDetail(BaseModel):
    role_id: int
    role_name: str
    role_description: Optional[str] = None
    assigned_at: Optional[str] = None
    assigned_by: Optional[int] = None
    assigned_by_name: Optional[str] = None
    effective_from: Optional[str] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True

class UserRoleAssign(BaseModel):
    role_id: int
    effective_from: Optional[str] = None
    expires_at: Optional[str] = None
    notes: Optional[str] = None

class UserRoleAssignmentResponse(BaseModel):
    success: bool = True
    active_permissions: List[str] = []
    menu_config: Optional[Any] = None
    user_id: Optional[int] = None
    role_id: Optional[int] = None
    message: Optional[str] = None

# ----- Bulk assign -----

class BulkAssignmentResult(BaseModel):
    user_id: int
    success: bool
    message: str

class BulkRoleAssignRequest(BaseModel):
    role_id: int
    user_ids: List[int]
class BulkRoleAssignResponse(BaseModel):
    total_requested: int
    total_success: int
    total_failed: int
    results: List[BulkAssignmentResult]

# ----- Role Transfer -----
class RoleTransferRequest(BaseModel):
    new_user_id: int
    role_id: int
    reason: Optional[str] = None

class RoleTransferResponse(BaseModel):
    success: bool
    message: str
    old_assignment_id: Optional[int] = None
    new_assignment_id: Optional[int] = None

# ----- Role Duplicate / Hierarchy -----

class RoleDuplicate(BaseModel):
    new_name: str
    description: Optional[str] = None

# ----- Permission Check -----

class PermissionCheckResponse(BaseModel):
    has_permission: bool
    granted_by_role: Optional[str] = None
    scope: Optional[str] = None


# ----- Access Paths -----

class AccessPathBase(BaseModel):
    path_pattern: str
    access_level: str

class AccessPathCreate(AccessPathBase):
    pass

class AccessPathUpdate(BaseModel):
    access_level: Optional[str] = None


class AccessPathRead(AccessPathBase):
    id: int
    user_id: int
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# Resolve forward references for self-referential models
RoleDetail.model_rebuild()
RoleHierarchy.model_rebuild()
