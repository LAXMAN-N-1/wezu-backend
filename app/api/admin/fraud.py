from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
from app.api import deps
from app.models.user import User
from app.models.fraud import RiskScore, Blacklist
from app.models.device_fingerprint import DeviceFingerprint, DuplicateAccount
from app.core.database import get_db

router = APIRouter()

# Admin-only fraud management

@router.get("/high-risk-users", response_model=List[dict])
def get_high_risk_users(
    threshold: float = 50.0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    """List users with high fraud risk scores"""
    high_risk = session.exec(
        select(RiskScore)
        .where(RiskScore.total_score >= threshold)
        .order_by(RiskScore.total_score.desc())
        .limit(limit)
    ).all()
    
    result = []
    for risk in high_risk:
        user = session.get(User, risk.user_id)
        result.append({
            "user_id": risk.user_id,
            "email": user.email if user else None,
            "phone": user.phone_number if user else None,
            "risk_score": risk.total_score,
            "breakdown": risk.breakdown,
            "last_updated": risk.last_updated
        })
    
    return result

@router.get("/duplicate-accounts", response_model=List[DuplicateAccount])
def get_duplicate_accounts(
    status: Optional[str] = None,
    min_confidence: float = 50.0,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    """Get potential duplicate accounts"""
    query = select(DuplicateAccount).where(
        DuplicateAccount.overall_confidence >= min_confidence
    )
    
    if status:
        query = query.where(DuplicateAccount.status == status)
    
    query = query.order_by(DuplicateAccount.overall_confidence.desc())
    
    duplicates = session.exec(query).all()
    return duplicates

class BlacklistAdd(BaseModel):
    type: str  # PHONE, EMAIL, IP, DEVICE_ID, PAN
    value: str
    reason: str

@router.post("/blacklist", response_model=Blacklist)
def add_to_blacklist(
    req: BlacklistAdd,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    """Add entry to blacklist"""
    # Check if already exists
    existing = session.exec(
        select(Blacklist)
        .where(Blacklist.type == req.type)
        .where(Blacklist.value == req.value)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already blacklisted")
    
    blacklist = Blacklist(
        type=req.type,
        value=req.value,
        reason=req.reason
    )
    session.add(blacklist)
    session.commit()
    session.refresh(blacklist)
    return blacklist

@router.get("/blacklist", response_model=List[Blacklist])
def get_blacklist(
    type: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    """Get blacklist entries"""
    query = select(Blacklist)
    if type:
        query = query.where(Blacklist.type == type)
    
    query = query.order_by(Blacklist.created_at.desc())
    return session.exec(query).all()

@router.delete("/blacklist/{id}")
def remove_from_blacklist(
    id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    """Remove from blacklist"""
    blacklist = session.get(Blacklist, id)
    if not blacklist:
        raise HTTPException(status_code=404, detail="Not found")
    
    session.delete(blacklist)
    session.commit()
    return {"status": "removed"}

@router.get("/device-fingerprints", response_model=List[dict])
def get_device_fingerprints(
    user_id: Optional[int] = None,
    suspicious_only: bool = False,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    """Get device fingerprints for analysis"""
    query = select(DeviceFingerprint)
    
    if user_id:
        query = query.where(DeviceFingerprint.user_id == user_id)
    
    if suspicious_only:
        query = query.where(DeviceFingerprint.is_suspicious == True)
    
    query = query.order_by(DeviceFingerprint.last_seen.desc()).limit(limit)
    
    fingerprints = session.exec(query).all()
    
    result = []
    for fp in fingerprints:
        user = session.get(User, fp.user_id) if fp.user_id else None
        result.append({
            "id": fp.id,
            "user_id": fp.user_id,
            "user_email": user.email if user else None,
            "device_id": fp.device_id,
            "device_type": fp.device_type,
            "os_name": fp.os_name,
            "ip_address": fp.ip_address,
            "is_suspicious": fp.is_suspicious,
            "risk_score": fp.risk_score,
            "first_seen": fp.first_seen,
            "last_seen": fp.last_seen
        })
    
    return result

class DuplicateAction(BaseModel):
    action: str  # MERGED, BLOCKED, FLAGGED, CLEARED
    notes: Optional[str] = None

@router.post("/duplicate-accounts/{id}/action")
def handle_duplicate_account(
    id: int,
    req: DuplicateAction,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    """Take action on duplicate account detection"""
    dup = session.get(DuplicateAccount, id)
    if not dup:
        raise HTTPException(status_code=404, detail="Not found")
    
    dup.action_taken = req.action
    dup.notes = req.notes
    dup.investigated_by = current_user.id
    dup.investigated_at = datetime.now(UTC)
    
    if req.action == "CONFIRMED":
        dup.status = "CONFIRMED"
    elif req.action == "CLEARED":
        dup.status = "FALSE_POSITIVE"
    else:
        dup.status = "INVESTIGATING"
    
    session.add(dup)
    session.commit()
    
    return {"status": "updated", "action": req.action}

from datetime import datetime, timezone; UTC = timezone.utc
