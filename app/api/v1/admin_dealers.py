"""
Admin: Dealer Management
Full CRUD + application pipeline + KYC + commission management for admin portal.
"""
from typing import Any, Optional, List, Dict
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, or_
from pydantic import BaseModel

from app.api import deps
from app.models.dealer import DealerProfile, DealerApplication, DealerDocument
from app.models.user import User
from app.models.station import Station
from app.models.commission import CommissionConfig, CommissionLog

router = APIRouter()


# ─── Schemas ───────────────────────────────────────────────────────────────

class DealerCreateRequest(BaseModel):
    email: str
    full_name: str
    password: str
    business_name: str
    contact_person: str
    contact_email: str
    contact_phone: str
    address_line1: str
    city: str
    state: str
    pincode: str
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None

class DealerUpdateRequest(BaseModel):
    business_name: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    is_active: Optional[bool] = None

class StageUpdateRequest(BaseModel):
    stage: str
    notes: Optional[str] = None

class CommissionConfigCreate(BaseModel):
    dealer_id: int
    transaction_type: str = "rental"
    percentage: float = 10.0
    flat_fee: float = 0.0

class CommissionConfigUpdate(BaseModel):
    percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    is_active: Optional[bool] = None


# ─── Helpers ───────────────────────────────────────────────────────────────

def _dealer_to_dict(dp: DealerProfile, user: User = None) -> dict:
    """Convert DealerProfile + User to a serializable dict."""
    d = {
        "id": dp.id,
        "user_id": dp.user_id,
        "business_name": dp.business_name,
        "contact_person": dp.contact_person,
        "contact_email": dp.contact_email,
        "contact_phone": dp.contact_phone,
        "address_line1": dp.address_line1,
        "city": dp.city,
        "state": dp.state,
        "pincode": dp.pincode,
        "gst_number": dp.gst_number,
        "pan_number": dp.pan_number,
        "is_active": dp.is_active,
        "created_at": dp.created_at.isoformat() if dp.created_at else None,
    }
    if user:
        d["user_email"] = user.email
        d["user_full_name"] = user.full_name
        d["user_type"] = user.user_type
        d["kyc_status"] = getattr(user, "kyc_status", None)
    return d


# ═══════════════════════════════════════════════════════════════════════════
# DEALER CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/")
def list_dealers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = None,
    city: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(deps.get_db),
):
    """List all dealers with optional search/filter/pagination."""
    query = select(DealerProfile)
    count_query = select(func.count(DealerProfile.id))

    if search:
        pattern = f"%{search}%"
        filter_cond = or_(
            DealerProfile.business_name.ilike(pattern),
            DealerProfile.contact_person.ilike(pattern),
            DealerProfile.contact_email.ilike(pattern),
        )
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    if city:
        query = query.where(DealerProfile.city.ilike(f"%{city}%"))
        count_query = count_query.where(DealerProfile.city.ilike(f"%{city}%"))

    if is_active is not None:
        query = query.where(DealerProfile.is_active == is_active)
        count_query = count_query.where(DealerProfile.is_active == is_active)

    total = db.exec(count_query).one()
    dealers = db.exec(query.offset(skip).limit(limit).order_by(DealerProfile.created_at.desc())).all()

    # Batch-load users for this page (eliminates N+1 db.get per dealer)
    user_ids = list({dp.user_id for dp in dealers if dp.user_id})
    users_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}

    results = []
    for dp in dealers:
        user = users_map.get(dp.user_id)
        results.append(_dealer_to_dict(dp, user))

    return {"dealers": results, "total_count": total}


@router.get("/stats")
def get_dealer_stats(db: Session = Depends(deps.get_db)):
    """Aggregated dealer statistics for the admin dashboard."""
    total_active = db.exec(
        select(func.count(DealerProfile.id)).where(DealerProfile.is_active == True)
    ).one()
    total_inactive = db.exec(
        select(func.count(DealerProfile.id)).where(DealerProfile.is_active == False)
    ).one()
    pending = db.exec(
        select(func.count(DealerApplication.id)).where(
            DealerApplication.current_stage.notin_(["APPROVED", "ACTIVE", "REJECTED"])
        )
    ).one()
    total_commissions = db.exec(
        select(func.coalesce(func.sum(CommissionLog.amount), 0.0))
    ).one()

    return {
        "totalActiveDealers": total_active,
        "totalInactiveDealers": total_inactive,
        "pendingOnboardings": pending,
        "totalCommissionsPaid": float(total_commissions),
    }


@router.post("/create")
def create_dealer(
    data: DealerCreateRequest,
    db: Session = Depends(deps.get_db),
):
    """Admin-initiated dealer creation."""
    from app.core.security import get_password_hash

    # Check duplicate email
    existing = db.exec(select(User).where(User.email == data.email)).first()
    if existing:
        raise HTTPException(400, "User with this email already exists")

    # Create user
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        user_type="DEALER",
        role_id=32,  # dealer role
    )
    db.add(user)
    db.flush()

    # Create dealer profile
    dp = DealerProfile(
        user_id=user.id,
        business_name=data.business_name,
        contact_person=data.contact_person,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        address_line1=data.address_line1,
        city=data.city,
        state=data.state,
        pincode=data.pincode,
        gst_number=data.gst_number,
        pan_number=data.pan_number,
        is_active=True,
    )
    db.add(dp)
    db.flush()

    # Create application record
    app = DealerApplication(dealer_id=dp.id, current_stage="APPROVED")
    app.log_stage("APPROVED", "Created by admin")
    db.add(app)
    db.commit()
    db.refresh(dp)

    return {"status": "success", "dealer_id": dp.id, "user_id": user.id}


@router.put("/{dealer_id}")
def update_dealer(
    dealer_id: int,
    data: DealerUpdateRequest,
    db: Session = Depends(deps.get_db),
):
    """Update dealer profile."""
    dp = db.get(DealerProfile, dealer_id)
    if not dp:
        raise HTTPException(404, "Dealer not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(dp, key, value)

    db.add(dp)
    db.commit()
    db.refresh(dp)
    return _dealer_to_dict(dp)


# ═══════════════════════════════════════════════════════════════════════════
# APPLICATION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/applications")
def list_applications(
    stage: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(deps.get_db),
):
    """List all dealer applications, optionally filtered by stage."""
    query = select(DealerApplication)
    if stage:
        query = query.where(DealerApplication.current_stage == stage)
    apps = db.exec(
        query.order_by(DealerApplication.updated_at.desc()).offset(skip).limit(limit)
    ).all()

    if not apps:
        return {"applications": [], "count": 0}

    # Batch-load DealerProfiles and Users to avoid N+1
    dealer_ids = list({a.dealer_id for a in apps if a.dealer_id})
    profiles = db.exec(select(DealerProfile).where(DealerProfile.id.in_(dealer_ids))).all() if dealer_ids else []
    profile_map = {dp.id: dp for dp in profiles}

    user_ids = list({dp.user_id for dp in profiles if dp.user_id})
    users = db.exec(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    user_map = {u.id: u for u in users}

    results = []
    for a in apps:
        dp = profile_map.get(a.dealer_id)
        user = user_map.get(dp.user_id) if dp else None
        results.append({
            "id": a.id,
            "dealer_id": a.dealer_id,
            "business_name": dp.business_name if dp else "Unknown",
            "contact_email": dp.contact_email if dp else "",
            "current_stage": a.current_stage,
            "risk_score": a.risk_score,
            "status_history": a.status_history or [],
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            "user_name": user.full_name if user else "",
        })
    return {"applications": results, "count": len(results)}


@router.put("/applications/{app_id}/stage")
def update_application_stage(
    app_id: int,
    data: StageUpdateRequest,
    db: Session = Depends(deps.get_db),
):
    """Advance, approve, or reject a dealer application."""
    VALID_STAGES = [
        "SUBMITTED", "AUTOMATED_CHECKS_PASSED", "KYC_SUBMITTED",
        "MANUAL_REVIEW_PASSED", "FIELD_VISIT_SCHEDULED", "FIELD_VISIT_COMPLETED",
        "REJECTED", "APPROVED", "TRAINING_COMPLETED", "ACTIVE"
    ]

    app = db.get(DealerApplication, app_id)
    if not app:
        raise HTTPException(404, "Application not found")

    if data.stage not in VALID_STAGES:
        raise HTTPException(400, f"Invalid stage. Valid: {VALID_STAGES}")

    app.log_stage(data.stage, data.notes or "")
    db.add(app)

    # Auto-activate dealer on APPROVED/ACTIVE
    if data.stage in ("APPROVED", "ACTIVE"):
        dp = db.get(DealerProfile, app.dealer_id)
        if dp:
            dp.is_active = True
            db.add(dp)

    # Deactivate on REJECTED
    if data.stage == "REJECTED":
        dp = db.get(DealerProfile, app.dealer_id)
        if dp:
            dp.is_active = False
            db.add(dp)

    db.commit()
    return {"status": "success", "new_stage": data.stage}


# ═══════════════════════════════════════════════════════════════════════════
# KYC / DOCUMENTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/kyc")
def list_kyc_documents(
    search: Optional[str] = None,
    doc_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(deps.get_db),
):
    """List all KYC documents across dealers."""
    query = select(DealerDocument)
    if doc_type:
        query = query.where(DealerDocument.document_type == doc_type)
    if search:
        # Push search into SQL instead of post-filter
        pattern = f"%{search}%"
        dealer_ids_q = select(DealerProfile.id).where(
            DealerProfile.business_name.ilike(pattern)
        )
        query = query.where(
            or_(
                DealerDocument.document_type.ilike(pattern),
                DealerDocument.dealer_id.in_(dealer_ids_q),
            )
        )
    docs = db.exec(
        query.order_by(DealerDocument.uploaded_at.desc()).offset(skip).limit(limit)
    ).all()

    # Batch-load dealer profiles to avoid N+1
    dealer_ids = list({d.dealer_id for d in docs if d.dealer_id})
    profiles = db.exec(select(DealerProfile).where(DealerProfile.id.in_(dealer_ids))).all() if dealer_ids else []
    profile_map = {dp.id: dp for dp in profiles}

    results = []
    for d in docs:
        dp = profile_map.get(d.dealer_id)
        results.append({
            "id": d.id,
            "dealer_id": d.dealer_id,
            "business_name": dp.business_name if dp else "Unknown",
            "document_type": d.document_type,
            "category": d.category,
            "file_url": d.file_url,
            "status": d.status,
            "is_verified": d.is_verified,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        })

    return results


@router.put("/documents/{doc_id}/verify")
def verify_document(
    doc_id: int,
    is_verified: bool = Query(...),
    db: Session = Depends(deps.get_db),
):
    """Verify or reject a KYC document."""
    doc = db.get(DealerDocument, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    doc.is_verified = is_verified
    doc.status = "VERIFIED" if is_verified else "REJECTED"
    db.add(doc)
    db.commit()
    return {"status": "success", "document_id": doc.id, "is_verified": is_verified}


@router.get("/documents/all")
def list_all_documents(
    search: Optional[str] = None,
    doc_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(deps.get_db),
):
    """List all dealer documents with optional filters."""
    query = select(DealerDocument)
    if doc_type:
        query = query.where(DealerDocument.document_type == doc_type)
    if search:
        pattern = f"%{search}%"
        dealer_ids_q = select(DealerProfile.id).where(
            DealerProfile.business_name.ilike(pattern)
        )
        query = query.where(DealerDocument.dealer_id.in_(dealer_ids_q))
    docs = db.exec(
        query.order_by(DealerDocument.uploaded_at.desc()).offset(skip).limit(limit)
    ).all()

    # Batch-load dealer profiles to avoid N+1
    dealer_ids = list({d.dealer_id for d in docs if d.dealer_id})
    profiles = db.exec(select(DealerProfile).where(DealerProfile.id.in_(dealer_ids))).all() if dealer_ids else []
    profile_map = {dp.id: dp for dp in profiles}

    results = []
    for d in docs:
        dp = profile_map.get(d.dealer_id)
        results.append({
            "id": d.id,
            "dealer_id": d.dealer_id,
            "business_name": dp.business_name if dp else "Unknown",
            "document_type": d.document_type,
            "file_url": d.file_url,
            "status": d.status,
            "is_verified": d.is_verified,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        })

    return results


# ═══════════════════════════════════════════════════════════════════════════
# COMMISSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/commissions/configs")
def list_commission_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(deps.get_db),
):
    """List all commission configurations."""
    configs = db.exec(
        select(CommissionConfig).order_by(CommissionConfig.created_at.desc()).offset(skip).limit(limit)
    ).all()

    # Batch-load dealer names to avoid N+1
    dealer_ids = list({c.dealer_id for c in configs if c.dealer_id})
    users = db.exec(select(User).where(User.id.in_(dealer_ids))).all() if dealer_ids else []
    user_map = {u.id: u for u in users}
    user_ids_list = [u.id for u in users]
    profiles = db.exec(select(DealerProfile).where(DealerProfile.user_id.in_(user_ids_list))).all() if user_ids_list else []
    profile_by_user = {dp.user_id: dp for dp in profiles}

    results = []
    for c in configs:
        dealer_name = "Global"
        if c.dealer_id:
            user = user_map.get(c.dealer_id)
            if user:
                dp = profile_by_user.get(user.id)
                dealer_name = dp.business_name if dp else user.full_name

        results.append({
            "id": c.id,
            "dealer_id": c.dealer_id,
            "dealer_name": dealer_name,
            "transaction_type": c.transaction_type,
            "percentage": c.percentage,
            "flat_fee": c.flat_fee,
            "is_active": c.is_active,
            "effective_from": c.effective_from.isoformat() if c.effective_from else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return results


@router.post("/commissions/configs")
def create_commission_config(
    data: CommissionConfigCreate,
    db: Session = Depends(deps.get_db),
):
    """Create a new commission configuration."""
    config = CommissionConfig(
        dealer_id=data.dealer_id,
        transaction_type=data.transaction_type,
        percentage=data.percentage,
        flat_fee=data.flat_fee,
        is_active=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return {"status": "success", "config_id": config.id}


@router.put("/commissions/configs/{config_id}")
def update_commission_config(
    config_id: int,
    data: CommissionConfigUpdate,
    db: Session = Depends(deps.get_db),
):
    """Update an existing commission configuration."""
    config = db.get(CommissionConfig, config_id)
    if not config:
        raise HTTPException(404, "Config not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)

    db.add(config)
    db.commit()
    return {"status": "success"}


@router.get("/commissions/logs")
def list_commission_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(deps.get_db),
):
    """Paginated commission logs."""
    logs = db.exec(
        select(CommissionLog).order_by(CommissionLog.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [
        {
            "id": l.id,
            "transaction_id": l.transaction_id,
            "dealer_id": l.dealer_id,
            "amount": l.amount,
            "status": l.status,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


@router.get("/commissions/stats")
def get_commission_stats(db: Session = Depends(deps.get_db)):
    """Summary statistics for commissions."""
    total_paid = db.exec(
        select(func.coalesce(func.sum(CommissionLog.amount), 0.0))
        .where(CommissionLog.status == "paid")
    ).one()
    total_pending = db.exec(
        select(func.coalesce(func.sum(CommissionLog.amount), 0.0))
        .where(CommissionLog.status == "pending")
    ).one()
    active_configs = db.exec(
        select(func.count(CommissionConfig.id)).where(CommissionConfig.is_active == True)
    ).one()

    return {
        "total_paid": float(total_paid),
        "total_pending": float(total_pending),
        "active_configs": active_configs,
    }


# Keep the dynamic dealer-id route after all static routes above. FastAPI route
# matching is order-sensitive; declaring /{dealer_id} earlier causes static
# paths like /applications or /kyc to be parsed as a dealer_id and return 422.
@router.get("/{dealer_id}")
def get_dealer_detail(dealer_id: int, db: Session = Depends(deps.get_db)):
    """Full dealer detail including profile, user, application, stations."""
    dp = db.get(DealerProfile, dealer_id)
    if not dp:
        raise HTTPException(404, "Dealer not found")

    user = db.get(User, dp.user_id)
    result = _dealer_to_dict(dp, user)

    app = db.exec(select(DealerApplication).where(DealerApplication.dealer_id == dp.id)).first()
    if app:
        result["application"] = {
            "id": app.id,
            "current_stage": app.current_stage,
            "risk_score": app.risk_score,
            "status_history": app.status_history or [],
            "created_at": app.created_at.isoformat() if app.created_at else None,
        }

    stations = db.exec(select(Station).where(Station.dealer_id == dp.id)).all()
    result["stations"] = [
        {"id": s.id, "name": s.name, "status": s.status, "city": s.city}
        for s in stations
    ]

    docs = db.exec(select(DealerDocument).where(DealerDocument.dealer_id == dp.id)).all()
    result["documents"] = [
        {
            "id": d.id,
            "document_type": d.document_type,
            "status": d.status,
            "is_verified": d.is_verified,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in docs
    ]

    return result
