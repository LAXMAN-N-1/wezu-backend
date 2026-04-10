from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC
from sqlalchemy import Column, JSON

class FraudAlertStatus(str):
    OPEN = "OPEN"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"

class FraudAlert(SQLModel, table=True):
    __tablename__ = "fraud_alerts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    alert_id: str = Field(unique=True, index=True) # e.g., FD-2026-00823
    
    user_id: int = Field(foreign_key="users.id", index=True)
    alert_type: str = Field(index=True) # SUSPICIOUS_LOGIN, UNUSUAL_TXN, ACCOUNT_TAKEOVER, MULTI_DEVICE, IMPOSSIBLE_TRAVEL
    
    risk_score: float = Field(default=0.0) # 0-100
    status: str = Field(default=FraudAlertStatus.OPEN, index=True)
    
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    resolved_at: Optional[datetime] = None
    resolved_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Metadata for the alert (e.g., matching device IDs, IP addresses, etc.)
    meta_data: Dict[str, Any] = Field(default={}, sa_column=Column("metadata", JSON))
    
    # Investigation notes
    # List of dicts: [{"admin_id": 1, "note": "...", "timestamp": "...", "admin_name": "..."}]
    investigation_notes: List[dict] = Field(default=[], sa_column=Column(JSON))
    
    # Relationships (if needed)
    # user = Relationship(back_populates="fraud_alerts") # Needs back_populates in User model
