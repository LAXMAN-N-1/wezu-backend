from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserSuspensionRequest(BaseModel):
    reason: str
    duration_days: Optional[int] = None # None = permanent

class UserRoleUpdateRequest(BaseModel):
    role_id: int
    reason: str

class BulkUserActionRequest(BaseModel):
    user_ids: List[int]
    action: str # activate, deactivate, message
    message: Optional[str] = None

class UserHistoryResponse(BaseModel):
    id: int
    action_type: str
    old_value: Optional[str]
    new_value: Optional[str]
    reason: Optional[str]
    actor_name: str
    created_at: datetime
