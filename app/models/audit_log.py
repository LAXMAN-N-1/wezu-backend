from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, UTC
from sqlalchemy import Column, JSON, DateTime, Index
from enum import Enum


# Standardized Audit Enum Constants
AUDIT_MODULES = ["auth", "dealer", "finance", "rental", "logistics", "api", "system"]
AUDIT_STATUSES = ["success", "failure", "unknown"]


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
    
    # 0. PostgreSQL Index Optimization requested by spec (DESC sort on timestamp)
    __table_args__ = (
        Index("ix_audit_logs_timestamp_desc", "timestamp", postgresql_using="btree", postgresql_ops={"timestamp": "DESC"}),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 1. Tracing & Session (advanced audit system)
    trace_id: Optional[str] = Field(default=None, index=True)      # Global request chain
    session_id: Optional[str] = Field(default=None, index=True)    # 32-char Session string
    action_id: Optional[str] = Field(default=None, index=True)     # 32-char Action string
    
    # 2. Structural Grouping
    role_prefix: Optional[str] = Field(default=None)               # DLR, ADM, CST, LOG
    level: str = Field(default="INFO")                             # INFO, WARNING, ERROR, CRITICAL
    
    user_id: Optional[int] = Field(default=None, index=True)  # Nullable for system actions
    action: str = Field(index=True)  # Standardized Action Code (e.g., FIN_UPD_BANK, DLR_UPD_PROFILE)
    module: Optional[str] = Field(default=None, index=True)        # auth, dealer, kyc, finance, etc.
    status: str = Field(default="success", index=True)            # success, failure
    resource_type: Optional[str] = None  # USER, BATTERY, STATION, WALLET, AUTH
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

    # Context & Network
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_method: Optional[str] = None
    endpoint: Optional[str] = None
    
    # Diagnostics & Errors
    response_time_ms: Optional[float] = None
    stack_trace: Optional[str] = None

    # Lifecycle - timestamp is fundamentally 'created_at' and explicitly indexed DESC above via table_args
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("timestamp", DateTime(timezone=True), index=True)
    )


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
