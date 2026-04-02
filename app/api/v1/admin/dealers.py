from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List, Optional, Any
from pydantic import BaseModel
from app.api import deps

from app.models.user import User
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.commission import CommissionLog
from app.services.dealer_service import DealerService
from app.services.settlement_service import SettlementService
from app.schemas.common import DataResponse
from app.schemas.dealer import (
    DealerProfileResponse, DealerApplicationUpdate, 
    FieldVisitSchedule, DealerRejectionRequest
)

router = APIRouter()

@router.get("/", response_model=DataResponse[List[DealerProfileResponse]])
def list_dealers(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: list all dealers with status filters"""
    # Logic to filter by stage if stage is provided 
    dealers = DealerService.get_dealers(session, skip=skip, limit=limit)
    return DataResponse(success=True, data=dealers)

@router.get("/{id}", response_model=DataResponse[dict])
def get_dealer_full_profile(
    id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: full dealer profile and onboarding details"""
    dealer = DealerService.get_dealer_by_id(session, id)
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
        
    app = session.exec(select(DealerApplication).where(DealerApplication.dealer_id == id)).first()
    return DataResponse(success=True, data={"profile": dealer, "application": app})

@router.put("/{id}/approve", response_model=DataResponse[dict])
def approve_dealer_stage(
    id: int,
    request: DealerApplicationUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: approve dealer at a specific onboarding stage"""
    app = session.exec(select(DealerApplication).where(DealerApplication.dealer_id == id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    updated_app = DealerService.update_application_stage(session, app.id, request.stage, request.notes or "Admin Approval")
    return DataResponse(success=True, data={"id": id, "stage": updated_app.current_stage})

@router.put("/{id}/reject", response_model=DataResponse[dict])
def reject_dealer_application(
    id: int,
    request: DealerRejectionRequest,
) -> Any:
    """Admin: reject dealer application with reason"""
    # Logic to record rejection in DB
    # We can use update_application_stage with REJECTED stage
    return DataResponse(success=True, data={"id": id, "status": "REJECTED", "reason": request.reason})

@router.post("/{id}/field-visit", response_model=DataResponse[dict])
def log_field_visit(
    id: int,
    request: FieldVisitSchedule,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: log field verification visit result or schedule"""
    # Find application
    app = session.exec(select(DealerApplication).where(DealerApplication.dealer_id == id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    visit = DealerService.schedule_field_visit(session, app.id, request.officer_id, request.scheduled_date)
    return DataResponse(success=True, data={"visit_id": visit.id, "status": visit.status})

@router.put("/commissions/{dealer_id}/rate", response_model=DataResponse[dict])
def set_dealer_commission_rate(
    dealer_id: int,
    rate: float,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: set or change commission rate for a dealer"""
    # Implement logic to update CommissionConfig
    return DataResponse(success=True, data={"dealer_id": dealer_id, "rate": rate})

@router.post("/settlements", response_model=DataResponse[dict])
def trigger_settlement(
    dealer_id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: trigger settlement payout to a dealer"""
    settlement = SettlementService.trigger_settlement(session, dealer_id)
    if not settlement:
        raise HTTPException(status_code=400, detail="No pending commissions for this dealer")
    return DataResponse(success=True, data={"settlement_id": settlement.id, "amount": settlement.amount})
@router.get("/commissions", response_model=DataResponse[list])
def admin_get_all_commissions(
    dealer_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
    session: Session = Depends(deps.get_db)
):
    """Admin: all commission records across dealers"""
    statement = select(CommissionLog)
    if dealer_id:
        statement = statement.where(CommissionLog.dealer_id == dealer_id)
    if status:
        statement = statement.where(CommissionLog.status == status)
        
    logs = session.exec(statement.order_by(CommissionLog.created_at.desc())).all()
    return DataResponse(success=True, data=logs)
