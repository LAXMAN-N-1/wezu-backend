from typing import Optional, List
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

RoleRead = RoleResponse

