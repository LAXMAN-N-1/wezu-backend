from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import Column, JSON

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, index=True) # Nullable for system actions
    action: str = Field(index=True) # LOGIN, LOGOUT, CREATE_USER, BATTERY_SWAP, etc.
    resource_type: str # USER, BATTERY, STATION, WALLET, AUTH
    resource_id: Optional[str] = None
    details: Optional[str] = None # Legacy text field (backward compat)
    meta_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column("metadata", JSON, nullable=True)) # Structured JSON context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None # Client user-agent string
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SecurityEvent(SQLModel, table=True):
    __tablename__ = "security_events"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(index=True) # failed_login, suspicious_ip, api_abuse
    severity: str = "medium" # low, medium, high, critical
    details: Optional[str] = None
    source_ip: Optional[str] = None
    user_id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_resolved: bool = Field(default=False)
