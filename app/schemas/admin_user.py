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


# --- Admin Create / Invite / Bulk-Invite ---

class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str
    phone_number: str
    password: Optional[str] = None        # auto-generated if omitted
    role_name: Optional[str] = None       # e.g. "customer", "admin"

class AdminInviteRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role_name: str                         # required role to assign

class BulkInviteRowResult(BaseModel):
    row_number: int
    email: Optional[str] = None
    success: bool
    error: Optional[str] = None

class BulkInviteResponse(BaseModel):
    success_count: int
    failure_count: int
    total_rows: int
    results: List[BulkInviteRowResult]
    emails_sent: int
    generated_at: datetime


# --- Invite Tracking & History ---

class UserInviteResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role_name: str
    status: str
    invited_by_name: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class UserInviteListResponse(BaseModel):
    items: List[UserInviteResponse]
    total_count: int
    page: int
    limit: int


class UserCreationHistoryItem(BaseModel):
    id: int
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    role_name: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    creation_method: str  # "direct", "invite", "bulk_invite", "self_registered"


class UserCreationHistoryResponse(BaseModel):
    items: List[UserCreationHistoryItem]
    total_count: int
    page: int
    limit: int
