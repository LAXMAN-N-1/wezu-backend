from typing import List, Optional
from pydantic import BaseModel

# Permission Schemas
class PermissionBase(BaseModel):
    slug: str
    module: str
    action: str
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class PermissionRead(PermissionBase):
    id: int
    
    class Config:
        from_attributes = True

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
    permissions: Optional[List[PermissionRead]] = None
    permission_count: int = 0
    category: str
    level: int
    parent_role_id: Optional[int] = None


    class Config:
        from_attributes = True

class RoleDetail(RoleRead):
    user_count: int = 0
    permission_tree: dict = {}
    parent_role: Optional["RoleRead"] = None
    child_roles: List["RoleRead"] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    level: Optional[int] = None
    parent_role_id: Optional[int] = None
    permissions: Optional[List[str]] = None # List of Permission Slugs

# User Assignment Schema
class UserRoleAssign(BaseModel):
    role_ids: List[int]
