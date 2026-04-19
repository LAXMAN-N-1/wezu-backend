from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import Any, List, Optional
from datetime import datetime, timezone; UTC = timezone.utc
from pydantic import BaseModel
from app.api import deps
from app.models.dealer import DealerProfile, DealerApplication, DealerDocument, FieldVisit
from app.models.commission import CommissionConfig, CommissionLog
from app.models.user import User
from app.core.database import get_db

router = APIRouter()

# --- Schemas ---

class ApplicationStageUpdate(BaseModel):
    stage: str
    notes: Optional[str] = None

class CommissionConfigUpdate(BaseModel):
    percentage: Optional[float] = None
    flat_fee: Optional[float] = None
    is_active: Optional[bool] = None

# --- Dealers ---

@router.get("/")
def list_dealers(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    city: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List all active dealers with search and city filters."""
    statement = select(DealerProfile).where(DealerProfile.is_active == True)
    
    if search:
        statement = statement.where(DealerProfile.business_name.ilike(f"%{search}%"))
    if city:
        statement = statement.where(DealerProfile.city.ilike(f"%{city}%"))
        
    count_stmt = select(func.count()).select_from(statement.subquery())
    total_count = db.exec(count_stmt).one()
    
    dealers = db.exec(statement.offset(skip).limit(limit)).all()
    
    return {
        "dealers": [d.model_dump() for d in dealers],
        "total_count": total_count
    }

@router.get("/stats")
def get_dealer_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Get high-level dealer network statistics."""
    total_dealers = db.exec(select(func.count(DealerProfile.id)).where(DealerProfile.is_active == True)).one()
    pending_applications = db.exec(select(func.count(DealerApplication.id)).where(DealerApplication.current_stage != "ACTIVE")).one()
    total_commissions = db.exec(select(func.sum(CommissionLog.amount))).one() or 0.0
    
    return {
        "total_active_dealers": total_dealers,
        "pending_onboardings": pending_applications,
        "total_commissions_paid": round(float(total_commissions), 2),
    }

# --- Onboarding Applications ---

@router.get("/applications")
def list_applications(
    stage: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List dealer onboarding applications in the queue."""
    statement = select(DealerApplication)
    if stage:
        statement = statement.where(DealerApplication.current_stage == stage)
    
    applications = db.exec(statement).all()
    
    dealer_ids = {app.dealer_id for app in applications if app.dealer_id}
    dealer_map = {d.id: d for d in db.exec(select(DealerProfile).where(DealerProfile.id.in_(dealer_ids))).all()} if dealer_ids else {}

    result = []
    for app in applications:
        dealer = dealer_map.get(app.dealer_id)
        result.append({
            "id": app.id,
            "dealer_id": app.dealer_id,
            "business_name": dealer.business_name if dealer else "Unknown",
            "current_stage": app.current_stage,
            "created_at": app.created_at,
            "updated_at": app.updated_at
        })
    return result

@router.put("/applications/{app_id}/stage")
def update_application_stage(
    app_id: int,
    update: ApplicationStageUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Update the onboarding stage for a dealer application."""
    application = db.get(DealerApplication, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Update history log
    history = list(application.status_history)
    history.append({
        "stage": update.stage,
        "timestamp": datetime.now(UTC).isoformat(),
        "notes": update.notes or ""
    })
    
    application.current_stage = update.stage
    application.status_history = history
    application.updated_at = datetime.now(UTC)
    
    if update.stage == "ACTIVE":
        dealer = db.get(DealerProfile, application.dealer_id)
        if dealer:
            dealer.is_active = True
            db.add(dealer)
            
    db.add(application)
    db.commit()
    return {"status": "success", "current_stage": application.current_stage}

# --- KYC & Documents ---

@router.get("/kyc")
def list_dealer_kyc(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List dealer documents with optional status filter."""
    if status_filter == "verified":
        documents = db.exec(select(DealerDocument).where(DealerDocument.is_verified == True)).all()
    elif status_filter == "rejected":
        # For now rejected = not verified (we can add a rejected field later)
        documents = db.exec(select(DealerDocument).where(DealerDocument.is_verified == False)).all()
    else:
        documents = db.exec(select(DealerDocument).where(DealerDocument.is_verified == False)).all()
    
    dealer_ids = {doc.dealer_id for doc in documents if doc.dealer_id}
    dealer_map = {d.id: d for d in db.exec(select(DealerProfile).where(DealerProfile.id.in_(dealer_ids))).all()} if dealer_ids else {}

    result = []
    for doc in documents:
        dealer = dealer_map.get(doc.dealer_id)
        result.append({
            "id": doc.id,
            "dealer_id": doc.dealer_id,
            "business_name": dealer.business_name if dealer else "Unknown",
            "document_type": doc.document_type,
            "file_url": doc.file_url,
            "is_verified": doc.is_verified,
            "uploaded_at": doc.uploaded_at
        })
    return result

@router.get("/documents/all")
def list_all_documents(
    search: Optional[str] = None,
    doc_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List all dealer documents across the network."""
    statement = select(DealerDocument)
    
    if doc_type:
        statement = statement.where(DealerDocument.document_type == doc_type)
    
    documents = db.exec(statement).all()
    
    dealer_ids = {doc.dealer_id for doc in documents if doc.dealer_id}
    dealer_map = {d.id: d for d in db.exec(select(DealerProfile).where(DealerProfile.id.in_(dealer_ids))).all()} if dealer_ids else {}

    result = []
    for doc in documents:
        dealer = dealer_map.get(doc.dealer_id)
        biz_name = dealer.business_name if dealer else "Unknown"
        
        if search and search.lower() not in biz_name.lower() and search.lower() not in doc.document_type.lower():
            continue
            
        result.append({
            "id": doc.id,
            "dealer_id": doc.dealer_id,
            "business_name": biz_name,
            "document_type": doc.document_type,
            "file_url": doc.file_url,
            "is_verified": doc.is_verified,
            "uploaded_at": doc.uploaded_at
        })
    return result

@router.put("/documents/{doc_id}/verify")
def verify_document(
    doc_id: int,
    is_verified: bool,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Approve or reject a dealer document."""
    doc = db.get(DealerDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc.is_verified = is_verified
    db.add(doc)
    db.commit()
    return {"status": "success", "is_verified": doc.is_verified}

# --- Single Dealer CRUD ---

@router.get("/{dealer_id}")
def get_dealer_detail(
    dealer_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Get full dealer profile details."""
    dealer = db.get(DealerProfile, dealer_id)
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    # Get documents count
    docs = db.exec(select(func.count(DealerDocument.id)).where(DealerDocument.dealer_id == dealer_id)).one()
    verified_docs = db.exec(select(func.count(DealerDocument.id)).where(
        DealerDocument.dealer_id == dealer_id,
        DealerDocument.is_verified == True
    )).one()
    
    # Get application status  
    application = db.exec(select(DealerApplication).where(DealerApplication.dealer_id == dealer_id)).first()
    
    result = dealer.model_dump()
    result["total_documents"] = docs
    result["verified_documents"] = verified_docs
    result["application_stage"] = application.current_stage if application else None
    
    return result

class DealerCreateRequest(BaseModel):
    business_name: str
    city: str
    contact_person: str
    contact_phone: str
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None

@router.post("/create")
def create_dealer(
    request: DealerCreateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Create a new dealer profile."""
    dealer = DealerProfile(
        user_id=current_user.id,
        business_name=request.business_name,
        city=request.city,
        contact_person=request.contact_person,
        contact_phone=request.contact_phone,
        gst_number=request.gst_number,
        pan_number=request.pan_number,
        is_active=True,
        commission_rate=10.0,
    )
    db.add(dealer)
    db.commit()
    db.refresh(dealer)
    
    # Auto-create application
    app = DealerApplication(
        dealer_id=dealer.id,
        current_stage="SUBMITTED",
        status_history=[{"stage": "SUBMITTED", "timestamp": datetime.now(UTC).isoformat(), "notes": "Created by admin"}],
    )
    db.add(app)
    db.commit()
    
    return {"status": "success", "dealer_id": dealer.id, "message": f"Dealer '{dealer.business_name}' created"}

class DealerUpdateRequest(BaseModel):
    business_name: Optional[str] = None
    city: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    is_active: Optional[bool] = None

@router.put("/{dealer_id}")
def update_dealer(
    dealer_id: int,
    request: DealerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Update dealer profile."""
    dealer = db.get(DealerProfile, dealer_id)
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(dealer, key, value)
    
    db.add(dealer)
    db.commit()
    db.refresh(dealer)
    return {"status": "success", "message": f"Dealer '{dealer.business_name}' updated"}

# --- Commissions ---

@router.get("/commissions/configs")
def list_commission_configs(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """List commission configurations for dealers."""
    configs = db.exec(select(CommissionConfig).where(CommissionConfig.dealer_id != None)).all()
    
    dealer_ids = {c.dealer_id for c in configs if c.dealer_id}
    dealer_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(dealer_ids))).all()} if dealer_ids else {}

    result = []
    for c in configs:
        dealer = dealer_map.get(c.dealer_id) if c.dealer_id else None
        result.append({
            "id": c.id,
            "dealer_id": c.dealer_id,
            "dealer_name": dealer.full_name if dealer else "N/A",
            "transaction_type": c.transaction_type,
            "percentage": c.percentage,
            "flat_fee": c.flat_fee,
            "is_active": c.is_active,
            "effective_from": c.effective_from.isoformat() if c.effective_from else None,
        })
    return result

@router.get("/commissions/stats")
def get_commission_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Get commission summary stats."""
    total_paid = db.exec(select(func.coalesce(func.sum(CommissionLog.amount), 0.0)).where(CommissionLog.status == "paid")).one()
    total_pending = db.exec(select(func.coalesce(func.sum(CommissionLog.amount), 0.0)).where(CommissionLog.status == "pending")).one()
    total_configs = db.exec(select(func.count(CommissionConfig.id)).where(CommissionConfig.is_active == True)).one()
    
    return {
        "total_paid": round(float(total_paid), 2),
        "total_pending": round(float(total_pending), 2),
        "active_configs": total_configs,
    }

class CommissionConfigCreate(BaseModel):
    dealer_id: Optional[int] = None
    transaction_type: str
    percentage: float = 0.0
    flat_fee: float = 0.0

@router.post("/commissions/configs")
def create_commission_config(
    request: CommissionConfigCreate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Create a new commission config."""
    config = CommissionConfig(
        dealer_id=request.dealer_id,
        transaction_type=request.transaction_type,
        percentage=request.percentage,
        flat_fee=request.flat_fee,
        is_active=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return {"status": "success", "config_id": config.id}

@router.put("/commissions/configs/{config_id}")
def update_commission_config(
    config_id: int,
    update: CommissionConfigUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """Update a dealer's commission configuration."""
    config = db.get(CommissionConfig, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if update.percentage is not None:
        config.percentage = update.percentage
    if update.flat_fee is not None:
        config.flat_fee = update.flat_fee
    if update.is_active is not None:
        config.is_active = update.is_active
        
    db.add(config)
    db.commit()
    return config

@router.get("/commissions/logs")
def list_commission_logs(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_admin),
):
    """View commission earnings log across the network."""
    statement = select(CommissionLog).order_by(CommissionLog.created_at.desc()).offset(skip).limit(limit)
    logs = db.exec(statement).all()
    
    dealer_ids = {log.dealer_id for log in logs if log.dealer_id}
    dealer_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(dealer_ids))).all()} if dealer_ids else {}

    result = []
    for log in logs:
        dealer = dealer_map.get(log.dealer_id) if log.dealer_id else None
        result.append({
            "id": log.id,
            "dealer_name": dealer.full_name if dealer else "Unknown",
            "amount": log.amount,
            "status": log.status,
            "created_at": log.created_at
        })
    return result

