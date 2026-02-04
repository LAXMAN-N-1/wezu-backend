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

class RoleCreate(RoleBase):
    permissions: List[str] # List of Permission Slugs

class RoleRead(RoleBase):
    id: int
    is_system_role: bool
    permissions: List[PermissionRead] = []

    class Config:
        from_attributes = True

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None # List of Permission Slugs

# User Assignment Schema
class UserRoleAssign(BaseModel):
    role_ids: List[int]
