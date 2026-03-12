from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, index=True) # Nullable for system actions
    action: str = Field(index=True) # login, create_rental, delete_user
    resource_type: str # user, rental, payment
    resource_id: Optional[str] = None
    details: Optional[str] = None # JSON string or text
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
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
