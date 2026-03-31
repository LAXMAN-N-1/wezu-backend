from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api.deps import get_db, get_current_active_user
from app.schemas.grn import GRNCreate, GRNResponse
from app.services.grn_service import GRNService
from app.models.user import User

router = APIRouter()

@router.post("/{indent_id}/receive", response_model=GRNResponse)
def receive_grn(
    *,
    session: Session = Depends(get_db),
    indent_id: int,
    grn_data: GRNCreate,
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.dealer_profile:
        raise HTTPException(status_code=403, detail="Not a dealer")
        
    service = GRNService(session)
    return service.receive_grn(current_user.dealer_profile.id, indent_id, grn_data, current_user.id)
