from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api import deps
from app.models.kyc import KYCDocument
from app.services.kyc_service import KYCService
from app.schemas.kyc import KYCDocumentResponse
from pydantic import BaseModel

router = APIRouter()

class KYCAction(BaseModel):
    reason: str = None

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
