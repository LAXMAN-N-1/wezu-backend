from __future__ import annotations
from typing import Optional, List, Any
from sqlmodel import SQLModel, Field
from datetime import datetime

class RoleBase(SQLModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = "shield"
    color: Optional[str] = "#4CAF50"
    is_active: bool = True

class RoleCreate(RoleBase):
    permissions: List[str] = [] # slugs
    parent_role_id: Optional[int] = None

class RoleUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    permissions: Optional[List[str]] = None # slugs
    parent_role_id: Optional[int] = None

class RoleRead(RoleBase):
    id: int
    user_count: int = 0
    active_user_count: int = 0
    permission_summary: str = ""
    is_system: bool = Field(default=False, alias="is_system")
    is_custom_role: bool = False
    scope_owner: str = "global"
    permissions_matrix: dict[str, list[str]] = Field(default={}, alias="permissions") # module -> list of actions
    created_at: datetime
    updated_at: Optional[datetime] = None

class RolePermissionRead(SQLModel):
    slug: str
    module: str
    action: str
    description: Optional[str] = None

class RoleDetail(RoleRead):
    permissions: List[RolePermissionRead] = []

class ModulePermission(SQLModel):
    module: str
    permissions: List[str] # ["view", "create", "edit", "delete"]

class PermissionMatrix(SQLModel):
    roles: List[str]
    modules: List[ModulePermission]
    matrix: Any # Dict of role -> module -> list of actions

class RoleAuditLog(SQLModel):
    action: str
    user_name: str
    timestamp: datetime
    details: Optional[str] = None
