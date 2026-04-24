from __future__ import annotations
"""
Audit log and security event schemas
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditLogListResponse(BaseModel):
    logs: List[AuditLogResponse]
    total_count: int
    page: int = 1
    limit: int = 20


class SecurityEventResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    event_type: str
    severity: str = "info"
    description: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SecurityEventListResponse(BaseModel):
    events: List[SecurityEventResponse]
    total_count: int
    page: int = 1
    limit: int = 20
