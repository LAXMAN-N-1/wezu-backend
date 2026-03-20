from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import Any, List, Optional
from datetime import datetime
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
    current_user: Any = Depends(deps.get_current_active_superuser),
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
    current_user: Any = Depends(deps.get_current_active_superuser),
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
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List dealer onboarding applications in the queue."""
    statement = select(DealerApplication)
    if stage:
        statement = statement.where(DealerApplication.current_stage == stage)
    
    applications = db.exec(statement).all()
    
    result = []
    for app in applications:
        dealer = db.get(DealerProfile, app.dealer_id)
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
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Update the onboarding stage for a dealer application."""
    application = db.get(DealerApplication, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Update history log
    history = list(application.status_history)
    history.append({
        "stage": update.stage,
        "timestamp": datetime.utcnow().isoformat(),
        "notes": update.notes or ""
    })
    
    application.current_stage = update.stage
    application.status_history = history
    application.updated_at = datetime.utcnow()
    
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
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List dealer documents awaiting verification."""
    documents = db.exec(select(DealerDocument).where(DealerDocument.is_verified == False)).all()
    
    result = []
    for doc in documents:
        dealer = db.get(DealerProfile, doc.dealer_id)
        result.append({
            "id": doc.id,
            "dealer_id": doc.dealer_id,
            "business_name": dealer.business_name if dealer else "Unknown",
            "document_type": doc.document_type,
            "file_url": doc.file_url,
            "uploaded_at": doc.uploaded_at
        })
    return result

@router.put("/documents/{doc_id}/verify")
def verify_document(
    doc_id: int,
    is_verified: bool,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Approve or reject a dealer document."""
    doc = db.get(DealerDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc.is_verified = is_verified
    db.add(doc)
    db.commit()
    return {"status": "success", "is_verified": doc.is_verified}

# --- Commissions ---

@router.get("/commissions/configs")
def list_commission_configs(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List commission configurations for dealers."""
    configs = db.exec(select(CommissionConfig).where(CommissionConfig.dealer_id != None)).all()
    return configs

@router.put("/commissions/configs/{config_id}")
def update_commission_config(
    config_id: int,
    update: CommissionConfigUpdate,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
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
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """View commission earnings log across the network."""
    statement = select(CommissionLog).order_by(CommissionLog.created_at.desc()).offset(skip).limit(limit)
    logs = db.exec(statement).all()
    
    result = []
    for log in logs:
        dealer = db.get(User, log.dealer_id) if log.dealer_id else None
        result.append({
            "id": log.id,
            "dealer_name": dealer.full_name if dealer else "Unknown",
            "amount": log.amount,
            "status": log.status,
            "created_at": log.created_at
        })
    return result
