from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, UTC
from sqlalchemy import Column, JSON
from enum import Enum


class AuditActionType(str, Enum):
    """Standardized action types for audit logging."""
    AUTH_LOGIN = "AUTH_LOGIN"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    DATA_MODIFICATION = "DATA_MODIFICATION"
    BALANCE_ADJUSTMENT = "BALANCE_ADJUSTMENT"
    USER_CREATION = "USER_CREATION"
    USER_INVITE = "USER_INVITE"
    PASSWORD_RESET = "PASSWORD_RESET"
    ACCOUNT_ACTIVATION = "ACCOUNT_ACTIVATION"
    SESSION_TERMINATED = "SESSION_TERMINATED"
    ACCOUNT_STATUS_CHANGE = "ACCOUNT_STATUS_CHANGE"
    PERMISSION_CHANGE = "PERMISSION_CHANGE"
    FINANCIAL_TRANSACTION = "FINANCIAL_TRANSACTION"


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, index=True)  # Nullable for system actions
    action: str = Field(index=True)  # AuditActionType value
    resource_type: str  # USER, BATTERY, STATION, WALLET, AUTH
    resource_id: Optional[str] = None  # Legacy string FK (backward compat)
    target_id: Optional[int] = Field(default=None, index=True)  # Typed FK to target entity
    details: Optional[str] = None  # Legacy text field (backward compat)
    meta_data: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column("metadata", JSON, nullable=True)
    )

    # Change tracking
    old_value: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column("old_value", JSON, nullable=True)
    )
    new_value: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column("new_value", JSON, nullable=True)
    )

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SecurityEvent(SQLModel, table=True):
    __tablename__ = "security_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    event_type: str = Field(index=True)  # failed_login, suspicious_ip, api_abuse
    severity: str = "medium"  # low, medium, high, critical
    details: Optional[str] = None
    source_ip: Optional[str] = None
    user_id: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_resolved: bool = Field(default=False)
