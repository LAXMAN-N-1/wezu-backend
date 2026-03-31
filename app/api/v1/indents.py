from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api.deps import get_db, get_current_active_user
from app.schemas.indent import IndentCreate, IndentApproveRequest, IndentResponse
from app.services.indent_service import IndentService
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=IndentResponse)
def create_indent(
    *,
    session: Session = Depends(get_db),
    indent_data: IndentCreate,
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.dealer_profile:
        raise HTTPException(status_code=403, detail="Not a dealer")
        
    service = IndentService(session)
    return service.create_indent(current_user.dealer_profile.id, indent_data)

@router.patch("/{indent_id}/approve", response_model=IndentResponse)
def approve_indent(
    *,
    session: Session = Depends(get_db),
    indent_id: int,
    approve_data: IndentApproveRequest,
    current_user: User = Depends(get_current_active_user)
):
    service = IndentService(session)
    return service.approve_indent(indent_id, approve_data)

@router.post("/{indent_id}/dispatch", response_model=IndentResponse)
def dispatch_indent(
    *,
    session: Session = Depends(get_db),
    indent_id: int,
    current_user: User = Depends(get_current_active_user)
):
    service = IndentService(session)
    return service.dispatch_indent(indent_id, current_user.id)
