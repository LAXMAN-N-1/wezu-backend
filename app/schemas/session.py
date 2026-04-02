"""
Session schemas: UserSession, SessionToken
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class UserSessionResponse(BaseModel):
    id: int
    user_id: int
    token_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    location: Optional[str] = None
    device_type: str = "unknown"
    is_active: bool = True
    last_active_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SessionListResponse(BaseModel):
    sessions: List[UserSessionResponse]
    total_count: int
