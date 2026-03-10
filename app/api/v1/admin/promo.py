from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api import deps
from app.api.deps import get_db
from app.models.user import User
from app.models.promo_code import PromoCode
from app.schemas.promo import PromoCreate, PromoUpdate, PromoResponse
from app.services.promo_service import PromoService

router = APIRouter()

@router.post("/", response_model=PromoResponse)
def create_coupon(
    *,
    session: Session = Depends(get_db),
    promo_in: PromoCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: create a coupon/promo code with rules"""
    promo = PromoCode.model_validate(promo_in)
    return PromoService.create_promo(session, promo)

@router.get("/", response_model=List[PromoResponse])
def list_coupons(
    *,
    session: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: list all coupons with usage stats"""
    return PromoService.list_all_promos(session)

@router.put("/{id}", response_model=PromoResponse)
def update_coupon(
    *,
    session: Session = Depends(deps.get_db),
    id: int,
    promo_in: PromoUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: update or deactivate a coupon"""
    update_data = promo_in.model_dump(exclude_unset=True)
    try:
        return PromoService.update_promo(session, id, update_data)
    except HTTPException as e:
        raise e
