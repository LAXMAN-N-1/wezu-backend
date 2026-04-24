from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status, Body, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from typing import List, Optional, Any
from datetime import datetime
from app.api import deps
from app.api.deps import get_current_user, get_db
from app.models.dealer import DealerProfile, DealerApplication, FieldVisit
from app.models.user import User
from app.services.dealer_service import DealerService
from app.schemas.common import DataResponse
from app.schemas.dealer import (
    DealerProfileCreate, DealerProfileUpdate, DealerProfileResponse,
    DealerApplicationUpdate, FieldVisitSchedule
)
from app.schemas.dealer_ledger import LedgerResponse, LedgerDetailResponse
from app.services.dealer_ledger_service import DealerLedgerService
from pydantic import BaseModel
from app.schemas.input_contracts import DealerPromotionCreate, DealerPromotionUpdate, BankAccountUpdate

class StageUpdate(BaseModel):
    stage: str
    note: str = ""

class VisitSchedule(BaseModel):
    application_id: int
    officer_id: int
    date: datetime
router = APIRouter()


# --- Dealer Profile CRUD ---

@router.post("/", response_model=DataResponse[DealerProfileResponse])
def create_dealer_profile(
    profile_in: DealerProfileCreate,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Create a new dealer profile (Onboarding)."""
    existing = DealerService.get_dealer_by_user(session, current_user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Dealer profile already exists")
    
    profile = DealerService.create_dealer_profile(session, current_user.id, profile_in.dict())
    return DataResponse(data=profile, message="Dealer profile created")

@router.get("/", response_model=DataResponse[List[DealerProfileResponse]])
def read_dealers(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(deps.get_db)
):
    """Retrieve all dealers."""
    # Add RBAC check here
    dealers = DealerService.get_dealers(session, skip=skip, limit=limit)
    return DataResponse(data=dealers)

@router.get("/registration-status", response_model=DataResponse[dict])
def get_registration_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: check their own onboarding stage and status"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Dealer profile not found")
    
    app = session.exec(select(DealerApplication).where(DealerApplication.dealer_id == profile.id)).first()
    return DataResponse(success=True, data={
        "business_name": profile.business_name,
        "current_stage": app.current_stage if app else "NOT_STARTED",
        "created_at": profile.created_at
    })

@router.get("/me/dashboard", response_model=DataResponse[dict])
def get_dealer_dashboard(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=403, detail="Access denied")
        
    stats = DealerService.get_dashboard_stats(session, profile.id)
    return DataResponse(data=stats)

# Admin Endpoints (Should be protected by superuser dependency in real app)
@router.post("/application/{app_id}/stage", response_model=DataResponse[DealerApplication])
def update_stage(
    app_id: int, 
    update_in: DealerApplicationUpdate,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    try:
        app = DealerService.update_application_stage(session, app_id, update_in.stage, update_in.notes or "")
        return DataResponse(data=app)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/visits/schedule", response_model=DataResponse[FieldVisit])
def schedule_visit(
    visit_in: FieldVisitSchedule,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(get_db)
):
    visit = DealerService.schedule_field_visit(session, visit_in.application_id, visit_in.officer_id, visit_in.date)
    return DataResponse(data=visit)

from app.services.financial_service import FinancialService
from app.models.settlement import Settlement
from app.services.settlement_service import SettlementService

class SettlementRequest(BaseModel):
    dealer_id: int
    start_date: datetime
    end_date: datetime

@router.post("/settlements/generate", response_model=DataResponse[Settlement])
def generate_settlement(
    req: SettlementRequest,
    current_user: User = Depends(deps.get_current_active_admin),
):
    # In real app verify admin
    settlement = FinancialService.generate_settlement(req.dealer_id, req.start_date, req.end_date)
    return DataResponse(data=settlement)

@router.get("/settlements", response_model=DataResponse[List[Settlement]])
def get_my_settlements(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
        
    settlements = session.exec(select(Settlement).where(Settlement.dealer_id == profile.id)).all()
    return DataResponse(success=True, data=settlements)

@router.get("/me/stations", response_model=DataResponse[list])
def get_dealer_stations(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: list of their own stations"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    from app.models.station import Station
    stations = session.exec(select(Station).where(Station.dealer_id == profile.id)).all()
    return DataResponse(success=True, data=stations)

@router.get("/me/transactions", response_model=DataResponse[LedgerResponse])
def get_dealer_transactions(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    txn_types: Optional[str] = None, # comma separated
    station_id: Optional[int] = None,
    search: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    status_types: Optional[str] = None, # comma separated
    limit: int = 50,
    skip: int = 0,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: Unified ledger of rentals, commissions, etc."""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    type_list = txn_types.split(",") if txn_types else None
    status_list = [s.strip().lower() for s in status_types.split(",")] if status_types else None
    
    ledger = DealerLedgerService.get_ledger_entries(
        db=session,
        dealer_id=profile.id,
        start_date=start_date,
        end_date=end_date,
        txn_types=type_list,
        station_id=station_id,
        search=search,
        amount_min=amount_min,
        amount_max=amount_max,
        status_types=status_list,
        limit=limit,
        skip=skip
    )
    return DataResponse(success=True, data=ledger)

@router.get("/me/transactions/export")
def export_dealer_transactions(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    txn_types: Optional[str] = None, # comma separated
    station_id: Optional[int] = None,
    search: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    status_types: Optional[str] = None, # comma separated
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: Export unified ledger of rentals, commissions, etc. as CSV"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    type_list = txn_types.split(",") if txn_types else None
    status_list = [s.strip().lower() for s in status_types.split(",")] if status_types else None
    
    csv_str = DealerLedgerService.generate_ledger_csv(
        db=session,
        dealer_id=profile.id,
        start_date=start_date,
        end_date=end_date,
        txn_types=type_list,
        station_id=station_id,
        search=search,
        amount_min=amount_min,
        amount_max=amount_max,
        status_types=status_list
    )
    
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dealer_transactions.csv"}
    )

@router.get("/me/transactions/{txn_id}", response_model=DataResponse[LedgerDetailResponse])
def get_dealer_transaction_details(
    txn_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
        
    try:
        detail = DealerLedgerService.get_ledger_detail(session, profile.id, txn_id)
        return DataResponse(success=True, data=detail)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/me/inventory", response_model=DataResponse[list])
def get_dealer_inventory(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: inventory across all their stations"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    from app.models.dealer_inventory import DealerInventory
    inventory = session.exec(select(DealerInventory).where(DealerInventory.dealer_id == profile.id)).all()
    return DataResponse(success=True, data=inventory)

@router.get("/me/commissions", response_model=DataResponse[list])
def get_dealer_commissions(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: commission history and pending amounts"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
        
    history = DealerService.get_commission_history(session, profile.id, skip, limit)
    return DataResponse(success=True, data=history)


@router.get("/me/commissions/{settlement_id}/settlement-pdf")
def get_dealer_settlement_pdf(
    settlement_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Dealer: download settlement PDF by settlement id."""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")

    settlement = session.get(Settlement, settlement_id)
    if not settlement or settlement.dealer_id != profile.id:
        raise HTTPException(status_code=404, detail="Settlement not found")

    path = SettlementService.generate_settlement_pdf(session, settlement_id)
    if not path:
        raise HTTPException(status_code=500, detail="Unable to generate settlement PDF")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"settlement_{settlement_id}.pdf",
    )

@router.get("/{id}", response_model=DataResponse[DealerProfileResponse])
def read_dealer(
    id: int,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(deps.get_db)
):
    """Get dealer by ID."""
    dealer = DealerService.get_dealer_by_id(session, id)
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    return DataResponse(data=dealer)

@router.put("/me", response_model=DataResponse[DealerProfileResponse])
def update_my_profile(
    profile_in: DealerProfileUpdate,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(deps.get_db)
):
    """Update current user's dealer profile."""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    dealer = DealerService.update_dealer_profile(session, profile.id, profile_in)
    return DataResponse(data=dealer, message="Profile updated")

@router.put("/{id}", response_model=DataResponse[DealerProfileResponse])
def update_dealer(
    id: int,
    profile_in: DealerProfileUpdate,
    current_user: User = Depends(deps.get_current_active_admin),
    session: Session = Depends(deps.get_db)
):
    """Update a specific dealer profile (Admin)."""
    dealer = DealerService.update_dealer_profile(session, id, profile_in)
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    return DataResponse(data=dealer, message="Profile updated")

@router.post("/me/documents", response_model=DataResponse[dict])
def upload_dealer_document(
    doc_type: str = Body(...),
    file_url: str = Body(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: upload business license, GST cert, insurance docs"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    from app.models.dealer import DealerDocument
    doc = DealerDocument(dealer_id=profile.id, document_type=doc_type, file_url=file_url)
    session.add(doc)
    session.commit()
    return DataResponse(success=True, data={"id": doc.id, "message": "Document uploaded"})

@router.get("/me/documents", response_model=DataResponse[list])
def list_dealer_documents(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: list uploaded documents with versions"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    from app.models.dealer import DealerDocument
    docs = session.exec(select(DealerDocument).where(DealerDocument.dealer_id == profile.id)).all()
    return DataResponse(success=True, data=docs)

@router.delete("/me/documents/{id}", response_model=DataResponse[dict])
def delete_dealer_document(
    id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Remove or replace a document"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    from app.models.dealer import DealerDocument
    doc = session.get(DealerDocument, id)
    if not doc or doc.dealer_id != profile.id:
        raise HTTPException(status_code=404, detail="Document not found")
        
    session.delete(doc)
    session.commit()
    return DataResponse(success=True, data={"message": "Document deleted"})

@router.post("/me/promotions", response_model=DataResponse[dict])
def create_dealer_promotion(
    request: DealerPromotionCreate = Body(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: create a discount/promotion campaign"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")

    from app.models.dealer_promotion import DealerPromotion
    promo = DealerPromotion(dealer_id=profile.id, **request.model_dump(exclude_unset=True))
    session.add(promo)
    session.commit()
    return DataResponse(success=True, data={"id": promo.id, "promo_code": promo.promo_code})

@router.get("/me/promotions", response_model=DataResponse[list])
def list_dealer_promotions(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: list all campaigns and their performance"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    from app.models.dealer_promotion import DealerPromotion
    promos = session.exec(select(DealerPromotion).where(DealerPromotion.dealer_id == profile.id)).all()
    return DataResponse(success=True, data=promos)

@router.get("/me/commission-statement/{month}")
def get_commission_statement(
    month: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Monthly commission statement PDF"""
    # Placeholder for actual PDF generation
    return {"message": f"Statement for {month} is being generated"}

@router.get("/me/support-tickets", response_model=DataResponse[list])
def get_dealer_support_tickets(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: view support tickets raised for their stations"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    # Placeholder
    return DataResponse(success=True, data=[])

@router.get("/me/sales", response_model=DataResponse[dict])
def get_dealer_sales(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: daily/weekly/monthly sales summary"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
        
    summary = DealerService.get_sales_summary(session, profile.id)
    return DataResponse(success=True, data=summary)

@router.put("/me/promotions/{id}", response_model=DataResponse[dict])
def update_dealer_promotion(
    id: int,
    request: DealerPromotionUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Update or deactivate a campaign"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
        
    try:
        promo = DealerService.update_promotion(session, id, profile.id, request)
        return DataResponse(success=True, data={"id": promo.id, "is_active": promo.is_active})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/me/bank-account", response_model=DataResponse[dict])
def get_bank_account(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: get verified bank account details for payouts"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    return DataResponse(success=True, data={"bank_details": profile.bank_details or {}})

@router.post("/me/bank-account", response_model=DataResponse[dict])
def update_bank_account(
    request: BankAccountUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """Dealer: submit or update bank details"""
    profile = DealerService.get_dealer_by_user(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Not a dealer")
    
    bank_data = request.model_dump()
    bank_data["verified"] = False
    
    profile.bank_details = bank_data
    session.add(profile)
    session.commit()
    
    return DataResponse(success=True, data={"message": "Bank account updated", "bank_details": bank_data})
