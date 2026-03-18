from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session
from typing import List, Optional
import uuid

from app.db.session import get_session
from app.models.user import User
from app.api.deps import get_current_user, get_current_active_admin as get_current_admin
from app.models.warranty_claim import ClaimStatus
from app.schemas.warranty import WarrantyClaimCreate, WarrantyClaimResponse, WarrantyClaimUpdate, WarrantyCheckResponse
from app.services.warranty_service import WarrantyService

customer_router = APIRouter()
admin_router = APIRouter()

# --- Customer Endpoints ---

@customer_router.post("/claims", response_model=WarrantyClaimResponse)
def submit_warranty_claim(
    claim_data: WarrantyClaimCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return WarrantyService.create_claim(db, current_user.id, claim_data)

@customer_router.get("/claims", response_model=List[WarrantyClaimResponse])
def get_my_warranty_claims(
    status: Optional[ClaimStatus] = Query(None, description="Filter claims by status"),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return WarrantyService.get_user_claims(db, current_user.id, status)

@customer_router.get("/claims/{claim_id}", response_model=WarrantyClaimResponse)
def get_my_warranty_claim(
    claim_id: uuid.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    claims = WarrantyService.get_user_claims(db, current_user.id)
    for claim in claims:
        if claim.id == claim_id:
            return claim
    raise HTTPException(status_code=404, detail="Claim not found")

@customer_router.get("/check/{order_id}", response_model=WarrantyCheckResponse)
def check_warranty_eligibility(
    order_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Basic eligibility check
    return WarrantyService.check_eligibility(db, order_id)

# --- Admin Endpoints ---

@admin_router.get("/claims", response_model=List[WarrantyClaimResponse])
def get_all_warranty_claims(
    status: Optional[ClaimStatus] = Query(None, description="Filter claims by status"),
    db: Session = Depends(get_session),
    current_admin: User = Depends(get_current_admin)
):
    return WarrantyService.get_all_claims(db, status)

@admin_router.put("/claims/{claim_id}/status", response_model=WarrantyClaimResponse)
def update_warranty_claim_status(
    claim_id: uuid.UUID,
    status_data: WarrantyClaimUpdate,
    db: Session = Depends(get_session),
    current_admin: User = Depends(get_current_admin)
):
    return WarrantyService.update_claim_status(db, claim_id, current_admin.id, status_data)
