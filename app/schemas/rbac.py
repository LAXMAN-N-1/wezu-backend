from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict

class PermissionResponse(BaseModel):
    id: int
    slug: str
    module: str
    action: str
    description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "system"
    level: int = 0
    is_active: bool = True

class RoleCreate(RoleBase):
    permission_ids: List[int] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    permission_ids: Optional[List[int]] = None

class RoleResponse(RoleBase):
    id: int
    permissions: List[PermissionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

class PermissionCheckResponse(BaseModel):
    has_permission: bool
    missing_permissions: List[str] = []

RoleDetail = RoleResponse
RoleRead = RoleResponse

PermissionRead = PermissionResponse

class PermissionCreate(BaseModel):
    slug: str
    module: str
    action: str
    description: Optional[str] = None

class PermissionItem(BaseModel):
    id: str
    label: str
    description: str
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
    permissions: List[str]
    mode: str = "overwrite"

class RolePermissionUpdateResponse(BaseModel):
    role_id: int
    users_affected: int
    active_permissions: List[str]

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

class BulkRoleAssignRequest(BaseModel):
    role_id: int
    user_ids: List[int]

class BulkAssignmentResult(BaseModel):
    user_id: int
    success: bool
    message: str

class BulkRoleAssignResponse(BaseModel):
    total_requested: int
    total_success: int
    total_failed: int
    results: List[BulkAssignmentResult]

class RoleTransferRequest(BaseModel):
    new_user_id: int
    role_id: int
    reason: Optional[str] = None

class RoleTransferResponse(BaseModel):
    success: bool
    message: str
    old_assignment_id: Optional[int] = None
    new_assignment_id: Optional[int] = None

class UserRoleAssign(BaseModel):
    role_id: int
    notes: Optional[str] = None
    effective_from: Optional[str] = None
    expires_at: Optional[str] = None

class UserRoleAssignmentResponse(BaseModel):
    success: bool
    active_permissions: List[str]
    menu_config: Optional[Any] = None

class RoleDuplicate(BaseModel):
    new_name: str
    description: Optional[str] = None

class AccessPathBase(BaseModel):
    path: str
    description: Optional[str] = None

class AccessPathCreate(AccessPathBase):
    pass

class AccessPathUpdate(BaseModel):
    path: Optional[str] = None
    description: Optional[str] = None

class AccessPathRead(AccessPathBase):
    id: int

class RoleHierarchy(BaseModel):
    id: int
    name: str
    level: int = 0
    parent_id: Optional[int] = None
    children: Optional[List["RoleHierarchy"]] = None
