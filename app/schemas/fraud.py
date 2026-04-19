from __future__ import annotations
"""
Fraud detection and security Pydantic schemas
Risk scores, verification, and device fingerprinting
"""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Union
from datetime import datetime

# Request Models
class PANVerificationRequest(BaseModel):
    """PAN verification request"""
    pan_number: str = Field(..., pattern=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
    name: str = Field(..., min_length=2)

class GSTVerificationRequest(BaseModel):
    """GST verification request"""
    gst_number: str = Field(..., pattern=r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$')
    business_name: str

class PhoneVerificationRequest(BaseModel):
    """Phone verification request"""
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{9,14}$')

class DeviceFingerprintSubmit(BaseModel):
    """Submit device fingerprint"""
    device_id: str = Field(..., min_length=10)
    fingerprint_hash: str = Field(..., min_length=32)
    device_type: str = Field(..., pattern=r'^(Union[MOBILE, TABLET|DESKTOP|OTHER])$')
    os_name: str
    os_version: Optional[str] = None
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    ip_address: str
    user_agent: Optional[str] = None
    canvas_fingerprint: Optional[str] = None
    webgl_fingerprint: Optional[str] = None
    device_metadata: Optional[Dict] = None

class BlacklistAdd(BaseModel):
    """Add to blacklist"""
    type: str = Field(..., pattern=r'^(Union[PHONE, EMAIL|IP|DEVICE_ID|PAN|GST])$')
    value: str = Field(..., min_length=3)
    reason: str = Field(..., min_length=10)
    severity: Optional[str] = Field("MEDIUM", pattern=r'^(Union[LOW, MEDIUM|HIGH|CRITICAL])$')

class DuplicateAccountAction(BaseModel):
    """Action on duplicate account"""
    action: str = Field(..., pattern=r'^(Union[MERGED, BLOCKED|FLAGGED|CLEARED])$')
    notes: Optional[str] = None

# Response Models
class RiskScoreResponse(BaseModel):
    """Risk score response"""
    id: int
    user_id: int
    total_score: float
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    breakdown: Dict
    contributing_factors: List[str]
    last_updated: datetime
    recommendations: Optional[List[str]]

    model_config = ConfigDict(from_attributes=True)

class VerificationResponse(BaseModel):
    """Verification result"""
    status: str  # PASS, FAIL, PENDING
    verified: bool
    details: str
    confidence_score: Optional[float] = None
    verification_timestamp: datetime
    provider: Optional[str] = None

class FraudCheckLogResponse(BaseModel):
    """Fraud check log response"""
    id: int
    user_id: int
    check_type: str
    status: str
    details: str
    performed_at: datetime
    ip_address: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class DeviceFingerprintResponse(BaseModel):
    """Device fingerprint response"""
    id: int
    user_id: int
    device_id: str
    fingerprint_hash: str
    device_type: str
    os_name: str
    browser_name: Optional[str]
    ip_address: str
    is_suspicious: bool
    risk_score: float
    first_seen: datetime
    last_seen: datetime
    total_logins: int

    model_config = ConfigDict(from_attributes=True)

class DuplicateAccountResponse(BaseModel):
    """Duplicate account detection response"""
    id: int
    primary_user_id: int
    suspected_duplicate_user_id: int
    matching_criteria: List[str]
    device_similarity_score: float
    behavior_similarity_score: Optional[float]
    overall_confidence: float
    status: str
    action_taken: Optional[str]
    investigated_at: Optional[datetime]
    notes: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class BlacklistResponse(BaseModel):
    """Blacklist entry response"""
    id: int
    type: str
    value: str
    reason: str
    severity: str
    created_at: datetime
    created_by: Optional[int]
    expires_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class HighRiskUserResponse(BaseModel):
    """High-risk user summary"""
    user_id: int
    email: Optional[str]
    phone: Optional[str]
    risk_score: float
    risk_level: str
    flags: List[str]
    recent_violations: int
    account_age_days: int
    last_activity: Optional[datetime]
    recommended_action: str

class FraudAnalyticsResponse(BaseModel):
    """Fraud analytics dashboard"""
    total_users_screened: int
    high_risk_users: int
    blocked_accounts: int
    blacklist_entries: int
    duplicate_accounts_detected: int
    verification_success_rate: float
    top_fraud_patterns: List[Dict]
    trend_data: Dict
