from __future__ import annotations
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api import deps
from app.services.promo_service import PromoService
from app.models.user import User
from pydantic import BaseModel

class PromoValidateRequest(BaseModel):
    code: str
    order_amount: float

class PromoApplyRequest(BaseModel):
    promo_id: int

router = APIRouter()

@router.post("/validate")
async def validate_promo(
    request: PromoValidateRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Customer: validate a coupon code and preview discount"""
    return PromoService.validate_promo(db, request.code, request.order_amount)

@router.post("/apply")
async def apply_promo(
    request: PromoApplyRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """Apply validated coupon to an active order"""
    success = PromoService.apply_promo(db, request.promo_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to apply promo")
    return {"message": "Promo code applied successfully"}
