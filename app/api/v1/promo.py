from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api import deps
from app.services.promo_service import PromoService
from app.models.user import User
from pydantic import BaseModel

class PromoValidateRequest(BaseModel):
    code: str
    order_amount: float

router = APIRouter()

@router.post("/validate")
async def validate_promo(
    request: PromoValidateRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    return PromoService.validate_promo(db, request.code, request.order_amount)
