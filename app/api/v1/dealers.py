from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from app.db.session import get_session
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.user import User
from app.services.dealer_service import DealerService
from app.api.deps import get_current_user
from app.schemas.common import DataResponse
from pydantic import BaseModel

router = APIRouter()

class DealerProfileCreate(BaseModel):
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

class StageUpdate(BaseModel):
    stage: str
    note: Optional[str] = ""

class VisitSchedule(BaseModel):
    application_id: int
    officer_id: int
    date: datetime

@router.post("/onboard", response_model=DataResponse[DealerProfile])
def submit_application(
    profile_in: DealerProfileCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Submits a new dealer application."""
    existing = DealerService.get_dealer_by_user(current_user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Dealer profile already exists")
    
    profile = DealerService.create_dealer_profile(current_user.id, profile_in.dict())
    return DataResponse(data=profile, message="Application submitted")

@router.get("/me", response_model=DataResponse[dict])
def get_my_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    profile = DealerService.get_dealer_by_user(current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
        
    app = session.exec(select(DealerApplication).where(DealerApplication.dealer_id == profile.id)).first()
    
    return DataResponse(data={
        "profile": profile,
        "application": app
    })

@router.get("/dashboard", response_model=DataResponse[dict])
def get_dashboard(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    profile = DealerService.get_dealer_by_user(current_user.id)
    if not profile:
        raise HTTPException(status_code=403, detail="Access denied")
        
    stats = DealerService.get_dashboard_stats(profile.id)
    return DataResponse(data=stats)

# Admin Endpoints (Should be protected by superuser dependency in real app)
@router.post("/application/{app_id}/stage", response_model=DataResponse[DealerApplication])
def update_stage(
    app_id: int, 
    update_in: StageUpdate,
    current_user: User = Depends(get_current_user), # Check Is Admin
    session: Session = Depends(get_session)
):
    try:
        app = DealerService.update_application_stage(app_id, update_in.stage, update_in.note)
        return DataResponse(data=app)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/visits/schedule", response_model=DataResponse[FieldVisit])
def schedule_visit(
    visit_in: VisitSchedule,
    current_user: User = Depends(get_current_user), # Check Is Admin
    session: Session = Depends(get_session)
):
    visit = DealerService.schedule_field_visit(visit_in.application_id, visit_in.officer_id, visit_in.date)
    return DataResponse(data=visit)

from app.services.financial_service import FinancialService
from app.models.commission import Settlement

class SettlementRequest(BaseModel):
    dealer_id: int
    start_date: datetime
    end_date: datetime

@router.post("/settlements/generate", response_model=DataResponse[Settlement])
def generate_settlement(
    req: SettlementRequest,
    current_user: User = Depends(get_current_user), # Admin check
):
    # In real app verify admin
    settlement = FinancialService.generate_settlement(req.dealer_id, req.start_date, req.end_date)
    return DataResponse(data=settlement)

@router.get("/settlements", response_model=DataResponse[List[Settlement]])
def get_my_settlements(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    profile = DealerService.get_dealer_by_user(current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
        
    settlements = session.exec(select(Settlement).where(Settlement.dealer_id == profile.id).order_by(Settlement.generated_at.desc())).all()
    return DataResponse(data=settlements)
