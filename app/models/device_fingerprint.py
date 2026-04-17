from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime, UTC
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.models.user import User

class DeviceFingerprint(SQLModel, table=True):
    __tablename__ = "device_fingerprints"
    """Track unique device characteristics for fraud detection"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Device identifiers
    device_id: str = Field(index=True)  # Unique device identifier
    fingerprint_hash: str = Field(index=True)  # Hash of device characteristics
    
    # Device information
    device_type: str  # MOBILE, TABLET, WEB
    os_name: str  # iOS, Android, Windows, macOS
    os_version: Optional[str] = None
    
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    
    device_model: Optional[str] = None
    device_manufacturer: Optional[str] = None
    
    # Screen and hardware
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    
    # Network information
    ip_address: str = Field(index=True)
    user_agent: Optional[str] = None
    
    # Advanced fingerprinting
    canvas_fingerprint: Optional[str] = None
    webgl_fingerprint: Optional[str] = None
    audio_fingerprint: Optional[str] = None
    
    # Additional metadata
    device_metadata: Optional[dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    # Risk indicators
    is_suspicious: bool = Field(default=False)
    risk_score: float = Field(default=0.0)
    
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: Optional["User"] = Relationship()
    duplicate_links: list["DuplicateAccount"] = Relationship(back_populates="device")

class DuplicateAccount(SQLModel, table=True):
    __tablename__ = "duplicate_accounts"
    """Link potentially duplicate accounts"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    primary_user_id: int = Field(foreign_key="users.id")
    suspected_duplicate_user_id: int = Field(foreign_key="users.id")
    
    # Evidence of duplication
    matching_device_id: Optional[int] = Field(default=None, foreign_key="device_fingerprints.id")
    matching_phone: bool = Field(default=False)
    matching_email: bool = Field(default=False)
    matching_ip: bool = Field(default=False)
    matching_address: bool = Field(default=False)
    matching_payment_method: bool = Field(default=False)
    
    # Similarity scores
    device_similarity_score: float = Field(default=0.0)  # 0-100
    behavior_similarity_score: float = Field(default=0.0)  # 0-100
    overall_confidence: float = Field(default=0.0)  # 0-100
    
    # Investigation status
    status: str = Field(default="DETECTED")  # DETECTED, INVESTIGATING, CONFIRMED, FALSE_POSITIVE
    
    investigated_by: Optional[int] = Field(default=None, foreign_key="users.id")
    investigated_at: Optional[datetime] = None
    
    action_taken: Optional[str] = None  # MERGED, BLOCKED, FLAGGED, CLEARED
    notes: Optional[str] = None
    
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    device: Optional[DeviceFingerprint] = Relationship(back_populates="duplicate_links")
    primary_user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[DuplicateAccount.primary_user_id]"})
    duplicate_user: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "[DuplicateAccount.suspected_duplicate_user_id]"})
    investigator: Optional["User"] = Relationship(sa_relationship_kwargs={"foreign_keys": "[DuplicateAccount.investigated_by]"})
