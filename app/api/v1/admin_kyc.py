from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from app.api import deps
from app.models.kyc import KYCDocument
from app.services.kyc_service import KYCService
from app.schemas.kyc import KYCDocumentResponse
from pydantic import BaseModel

router = APIRouter()

class KYCAction(BaseModel):
    reason: str = None

from datetime import datetime
from app.schemas.kyc import KYCDocumentResponse, KYCQueueItem, KYCQueueResponse
from app.models.user import User

@router.get("/pending", response_model=KYCQueueResponse)
def get_pending_kyc_queue(
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
    page: int = 1,
    size: int = 10,
    user_type: str = None, # dealer, customer (optional filter)
) -> Any:
    """
    List all users with pending KYC verification.
    """
    offset = (page - 1) * size
    
    # 1. Base Query: Users with pending status
    query = select(User).where(User.kyc_status == "pending_verification")
    
    # 2. Filter by User Type (Role) if provided
    # Note: This assumes Role integration. If simplistic, we might just return all.
    # For now, we fetch all pending users and filter/enrich in python to avoid complex joins if models aren't perfectly aligned
    # Optimization: If user count is high, we MUST do this at DB layer.
    
    total = db.exec(select(func.count()).select_from(query.subquery())).one()
    users = db.exec(query.offset(offset).limit(size)).all()
    
    items = []
    for user in users:
        # Fetch documents
        docs = db.exec(select(KYCDocument).where(KYCDocument.user_id == user.id)).all()
        
        # Determine User Type (Basic logic for now)
        # In a real scenario, we'd check user.roles
        u_type = "customer"
        # if user.roles and any(r.name == "dealer" for r in user.roles): u_type = "dealer"

        # Determine submission time (latest doc upload)
        submitted_at = max([d.uploaded_at for d in docs]) if docs else None

        items.append(KYCQueueItem(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            user_type=u_type,
            submitted_at=submitted_at,
            documents=docs
        ))
        
    return KYCQueueResponse(
        items=items,
        total=total,
        page=page,
        size=size
    )

@router.get("/documents/pending", response_model=List[KYCDocumentResponse])
def get_pending_documents(
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    List all documents waiting for verification.
    """
    docs = db.exec(select(KYCDocument).where(KYCDocument.status == "pending")).all()
    return docs

@router.post("/documents/{doc_id}/approve", response_model=KYCDocumentResponse)
def approve_document(
    doc_id: int,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Approve a KYC document.
    """
    doc = KYCService.approve_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.post("/documents/{doc_id}/reject", response_model=KYCDocumentResponse)
def reject_document(
    doc_id: int,
    action: KYCAction,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Reject a KYC document with a reason.
    """
    if not action.reason:
        raise HTTPException(status_code=400, detail="Reason is required for rejection")
    
    doc = KYCService.reject_document(db, doc_id, action.reason)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
