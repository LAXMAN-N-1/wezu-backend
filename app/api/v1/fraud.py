from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from app.api import deps
from app.models.user import User
from app.models.fraud import RiskScore, FraudCheckLog
from app.models.device_fingerprint import DeviceFingerprint, DuplicateAccount

router = APIRouter()

# Schemas
class PANVerifyRequest(BaseModel):
    pan_number: str
    name: str

class GSTVerifyRequest(BaseModel):
    gst_number: str
    business_name: str

class PhoneCheckRequest(BaseModel):
    phone_number: str

class DeviceFingerprintSubmit(BaseModel):
    device_id: str
    fingerprint_hash: str
    device_type: str
    os_name: str
    os_version: Optional[str] = None
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    ip_address: str
    user_agent: Optional[str] = None
    device_metadata: Optional[dict] = None

# User Endpoints
@router.get("/users/{user_id}/risk-score", response_model=RiskScore)
def get_user_risk_score(
    user_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Get fraud risk score for a user (admin or self)"""
    # Allow users to see their own score or admins to see any
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    risk_score = session.exec(
        select(RiskScore).where(RiskScore.user_id == user_id)
    ).first()
    
    if not risk_score:
        # Create default risk score
        risk_score = RiskScore(
            user_id=user_id,
            total_score=0.0,
            breakdown={"initial": "No fraud checks performed yet"}
        )
        session.add(risk_score)
        session.commit()
        session.refresh(risk_score)
    
    return risk_score

@router.post("/verify/pan")
def verify_pan(
    req: PANVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Verify PAN number (mock implementation)"""
    # In production, integrate with government API
    # For now, basic validation
    
    if len(req.pan_number) != 10:
        status = "FAIL"
        details = "Invalid PAN format"
    else:
        status = "PASS"
        details = "PAN verified successfully"
    
    # Log the check
    log = FraudCheckLog(
        user_id=current_user.id,
        check_type="PAN_VERIFY",
        status=status,
        details=details
    )
    session.add(log)
    
    # Update risk score if failed
    if status == "FAIL":
        risk_score = session.exec(
            select(RiskScore).where(RiskScore.user_id == current_user.id)
        ).first()
        if risk_score:
            risk_score.total_score += 20  # Penalty for failed PAN
            session.add(risk_score)
    
    session.commit()
    
    return {"status": status, "details": details}

@router.post("/verify/gst")
def verify_gst(
    req: GSTVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Verify GST number (mock implementation)"""
    # In production, integrate with GST API
    
    if len(req.gst_number) != 15:
        status = "FAIL"
        details = "Invalid GST format"
    else:
        status = "PASS"
        details = "GST verified successfully"
    
    log = FraudCheckLog(
        user_id=current_user.id,
        check_type="GST_VERIFY",
        status=status,
        details=details
    )
    session.add(log)
    session.commit()
    
    return {"status": status, "details": details}

@router.post("/verify/phone")
def verify_phone(
    req: PhoneCheckRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Check phone number for fraud indicators"""
    from app.models.fraud import Blacklist
    
    # Check blacklist
    blacklisted = session.exec(
        select(Blacklist)
        .where(Blacklist.type == "PHONE")
        .where(Blacklist.value == req.phone_number)
    ).first()
    
    if blacklisted:
        status = "FAIL"
        details = f"Phone number blacklisted: {blacklisted.reason}"
    else:
        status = "PASS"
        details = "Phone number clean"
    
    log = FraudCheckLog(
        user_id=current_user.id,
        check_type="PHONE_CHECK",
        status=status,
        details=details
    )
    session.add(log)
    session.commit()
    
    return {"status": status, "details": details, "risk_level": "HIGH" if blacklisted else "LOW"}

@router.post("/device/fingerprint", response_model=DeviceFingerprint)
def submit_device_fingerprint(
    req: DeviceFingerprintSubmit,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Submit device fingerprint for tracking"""
    from datetime import datetime, UTC
    
    # Check if device already exists
    existing = session.exec(
        select(DeviceFingerprint)
        .where(DeviceFingerprint.device_id == req.device_id)
        .where(DeviceFingerprint.user_id == current_user.id)
    ).first()
    
    if existing:
        # Update last seen
        existing.last_seen = datetime.now(UTC)
        existing.ip_address = req.ip_address
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    
    # Create new fingerprint
    fingerprint = DeviceFingerprint(
        user_id=current_user.id,
        device_id=req.device_id,
        fingerprint_hash=req.fingerprint_hash,
        device_type=req.device_type,
        os_name=req.os_name,
        os_version=req.os_version,
        browser_name=req.browser_name,
        browser_version=req.browser_version,
        ip_address=req.ip_address,
        user_agent=req.user_agent,
        device_metadata=req.device_metadata,
        is_suspicious=False,
        risk_score=0.0
    )
    session.add(fingerprint)
    
    # Check for duplicate devices (same device, different user)
    duplicate_device = session.exec(
        select(DeviceFingerprint)
        .where(DeviceFingerprint.device_id == req.device_id)
        .where(DeviceFingerprint.user_id != current_user.id)
    ).first()
    
    if duplicate_device:
        # Flag potential duplicate account
        dup_account = DuplicateAccount(
            primary_user_id=duplicate_device.user_id,
            suspected_duplicate_user_id=current_user.id,
            matching_device_id=duplicate_device.id,
            device_similarity_score=95.0,
            overall_confidence=75.0,
            status="DETECTED"
        )
        session.add(dup_account)
        
        # Increase risk score
        risk_score = session.exec(
            select(RiskScore).where(RiskScore.user_id == current_user.id)
        ).first()
        if risk_score:
            risk_score.total_score += 30
            session.add(risk_score)
    
    session.commit()
    session.refresh(fingerprint)
    return fingerprint
