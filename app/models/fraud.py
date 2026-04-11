from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, UTC
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

class RiskScore(SQLModel, table=True):
    __tablename__ = "risk_scores"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", unique=True)
    
    total_score: float = Field(default=0.0) # 0-100 (High is bad)
    breakdown: Optional[dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
class FraudCheckLog(SQLModel, table=True):
    __tablename__ = "fraud_check_logs"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    check_type: str # PAN_VERIFY, IP_CHECK, DEVICE_FINGERPRINT
    status: str # PASS, FAIL, WARN
    details: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class Blacklist(SQLModel, table=True):
    __tablename__ = "blacklists"
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str # PHONE, EMAIL, IP, DEVICE_ID, PAN
    value: str = Field(index=True, unique=True)
    reason: str
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
