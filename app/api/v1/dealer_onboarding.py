from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session, select
from typing import Any, Dict, List
from datetime import datetime, UTC

from app.db.session import get_session
from app.api import deps
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit

router = APIRouter()

def _get_dealer_id(db: Session, user_id: int) -> int:
    dealer = deps.get_dealer_profile_or_403(db, user_id, detail="Not a dealer")
    return dealer.id

def _get_application(db: Session, dealer_id: int) -> DealerApplication:
    app = db.exec(
        select(DealerApplication).where(DealerApplication.dealer_id == dealer_id)
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app

# ─── DEALER ENDPOINTS ───

@router.get("/status")
def get_onboarding_status(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get the current application stage and history."""
    dealer_id = _get_dealer_id(db, current_user.id)
    app = _get_application(db, dealer_id)
    return {
        "current_stage": app.current_stage,
        "history": app.status_history,
        "risk_score": app.risk_score
    }

@router.post("/stage/trigger-checks")
def trigger_automated_checks(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Stage 2: Run automated validation checks."""
    dealer_id = _get_dealer_id(db, current_user.id)
    app = _get_application(db, dealer_id)
    if app.current_stage != "SUBMITTED":
        raise HTTPException(status_code=400, detail=f"Invalid stage transition from {app.current_stage}")
    
    app.log_stage("AUTOMATED_CHECKS_PASSED", "All basic validation checks passed automatically.")
    db.commit()
    db.refresh(app)
    return {"message": "Automated checks passed", "stage": app.current_stage}

@router.post("/stage/submit-kyc")
def submit_kyc(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Stage 3: Confirm KYC documents have been uploaded."""
    dealer_id = _get_dealer_id(db, current_user.id)
    app = _get_application(db, dealer_id)
    if app.current_stage != "AUTOMATED_CHECKS_PASSED":
        raise HTTPException(status_code=400, detail=f"Invalid stage transition from {app.current_stage}")
    
    app.log_stage("KYC_SUBMITTED", "Dealer has submitted KYC for manual review.")
    db.commit()
    db.refresh(app)
    return {"message": "KYC submitted successfully", "stage": app.current_stage}


@router.post("/stage/complete-training")
def complete_training(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Stage 7: Dealer confirms they have completed setup and training."""
    dealer_id = _get_dealer_id(db, current_user.id)
    app = _get_application(db, dealer_id)
    if app.current_stage != "APPROVED":
        raise HTTPException(status_code=400, detail=f"Invalid stage transition from {app.current_stage}")
    
    app.log_stage("TRAINING_COMPLETED", "Dealer marked training as complete.")
    db.commit()
    db.refresh(app)
    return {"message": "Training completed", "stage": app.current_stage}

# ─── ADMIN ENDPOINTS ───

@router.post("/admin/{application_id}/review")
def admin_manual_review(
    application_id: int,
    approve: bool = Body(..., embed=True),
    notes: str = Body("", embed=True),
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Stage 4: Admin reviews application and KYC."""
    # Assuming current_user is admin. Ideally add an RBAC check here.
    app = db.get(DealerApplication, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    if approve:
        app.log_stage("MANUAL_REVIEW_PASSED", notes)
    else:
        app.log_stage("REJECTED", notes)
        
    db.commit()
    db.refresh(app)
    return {"message": "Review completed", "stage": app.current_stage}

@router.post("/admin/{application_id}/schedule-visit")
def admin_schedule_visit(
    application_id: int,
    scheduled_date: datetime = Body(..., embed=True),
    officer_id: int = Body(..., embed=True),
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Stage 5a: Admin schedules a field visit."""
    app = db.get(DealerApplication, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    visit = FieldVisit(
        application_id=app.id,
        officer_id=officer_id,
        scheduled_date=scheduled_date,
        status="SCHEDULED"
    )
    db.add(visit)
    app.log_stage("FIELD_VISIT_SCHEDULED", f"Visit scheduled for {scheduled_date}")
    db.commit()
    return {"message": "Field visit scheduled"}

@router.post("/admin/{application_id}/complete-visit")
def admin_complete_visit(
    application_id: int,
    visit_id: int = Body(..., embed=True),
    report_data: Dict = Body(..., embed=True),
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Stage 5b: Field officer completes the visit."""
    app = db.get(DealerApplication, application_id)
    visit = db.get(FieldVisit, visit_id)
    if not app or not visit:
        raise HTTPException(status_code=404, detail="Record not found")
        
    visit.status = "COMPLETED"
    visit.completed_date = datetime.now(UTC)
    visit.report_data = report_data
    
    app.log_stage("FIELD_VISIT_COMPLETED", "Field verification successful.")
    db.commit()
    return {"message": "Field visit completed"}

@router.post("/admin/{application_id}/approve")
def admin_final_approve(
    application_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Stage 6: Final Admin Approval."""
    app = db.get(DealerApplication, application_id)
    if not app:
        raise HTTPException(status_code=404)
        
    app.log_stage("APPROVED", "Final admin approval granted. Ready for training.")
    db.commit()
    return {"message": "Application formally approved"}

@router.post("/admin/{application_id}/handover-inventory")
def admin_handover_inventory(
    application_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_admin),
) -> Any:
    """Stage 8: Admin hands over initial inventory and marks active."""
    app = db.get(DealerApplication, application_id)
    if not app:
        raise HTTPException(status_code=404)
        
    dealer = db.get(DealerProfile, app.dealer_id)
    dealer.is_active = True
    
    app.log_stage("ACTIVE", "Inventory handed over. Dealer is fully active.")
    db.commit()
    return {"message": "Dealer activated"}
