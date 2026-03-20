from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from typing import Any, List, Optional
from datetime import datetime, date
from pydantic import BaseModel
from app.api import deps
from app.models.user import User, KYCStatus
from app.models.kyc import KYCDocument, KYCDocumentStatus
from app.core.database import get_db

router = APIRouter()


class KYCRejectRequest(BaseModel):
    reason: str


@router.get("/")
def list_kyc_documents(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,  # pending, verified, rejected
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """List all KYC documents with user details, filterable by status."""
    statement = select(KYCDocument)

    if status:
        statement = statement.where(KYCDocument.status == status)

    count_stmt = select(func.count()).select_from(statement.subquery())
    total_count = db.exec(count_stmt).one()

    statement = statement.order_by(KYCDocument.uploaded_at.desc()).offset(skip).limit(limit)
    documents = db.exec(statement).all()

    result = []
    for doc in documents:
        # Fetch user info
        user = db.get(User, doc.user_id)
        result.append({
            "id": doc.id,
            "user_id": doc.user_id,
            "user_name": user.full_name if user else "Unknown",
            "user_email": user.email if user else "",
            "user_phone": user.phone_number if user else "",
            "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else str(doc.document_type),
            "document_number": doc.document_number,
            "file_url": doc.file_url,
            "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
            "rejection_reason": doc.rejection_reason,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "verified_at": doc.verified_at.isoformat() if doc.verified_at else None,
            "verified_by": doc.verified_by,
        })

    return {
        "documents": result,
        "total_count": total_count,
        "page": skip // limit + 1 if limit > 0 else 1,
        "page_size": limit,
    }


@router.get("/stats")
def get_kyc_stats(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get KYC dashboard statistics."""
    total_pending = db.exec(
        select(func.count()).where(KYCDocument.status == "pending")
    ).one()

    total_verified = db.exec(
        select(func.count()).where(KYCDocument.status == "verified")
    ).one()

    total_rejected = db.exec(
        select(func.count()).where(KYCDocument.status == "rejected")
    ).one()

    total_documents = db.exec(select(func.count()).select_from(KYCDocument)).one()

    # Users with pending KYC
    pending_users = db.exec(
        select(func.count()).where(User.kyc_status == KYCStatus.PENDING, User.is_deleted == False)
    ).one()

    return {
        "total_documents": total_documents,
        "total_pending": total_pending,
        "total_verified": total_verified,
        "total_rejected": total_rejected,
        "pending_users": pending_users,
    }


@router.get("/{doc_id}")
def get_document_detail(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Get a single KYC document with user details."""
    doc = db.get(KYCDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    user = db.get(User, doc.user_id)

    return {
        "id": doc.id,
        "user_id": doc.user_id,
        "user_name": user.full_name if user else "Unknown",
        "user_email": user.email if user else "",
        "user_phone": user.phone_number if user else "",
        "user_kyc_status": user.kyc_status.value if user and hasattr(user.kyc_status, 'value') else str(user.kyc_status) if user else None,
        "document_type": doc.document_type.value if hasattr(doc.document_type, 'value') else str(doc.document_type),
        "document_number": doc.document_number,
        "file_url": doc.file_url,
        "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
        "rejection_reason": doc.rejection_reason,
        "verification_response": doc.verification_response,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "verified_at": doc.verified_at.isoformat() if doc.verified_at else None,
        "verified_by": doc.verified_by,
    }


@router.put("/{doc_id}/approve")
def approve_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Approve a KYC document."""
    doc = db.get(KYCDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = KYCDocumentStatus.VERIFIED
    doc.verified_at = datetime.utcnow()
    doc.verified_by = current_user.id
    db.add(doc)

    # Check if all documents for this user are verified => approve user KYC
    user_docs = db.exec(select(KYCDocument).where(KYCDocument.user_id == doc.user_id)).all()
    all_verified = all(d.status == KYCDocumentStatus.VERIFIED or d.id == doc_id for d in user_docs)

    if all_verified:
        user = db.get(User, doc.user_id)
        if user:
            user.kyc_status = KYCStatus.APPROVED
            user.updated_at = datetime.utcnow()
            db.add(user)

    db.commit()
    db.refresh(doc)

    return {"status": "success", "message": "Document approved", "doc_status": "verified"}


@router.put("/{doc_id}/reject")
def reject_document(
    doc_id: int,
    request: KYCRejectRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Reject a KYC document with reason."""
    doc = db.get(KYCDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = KYCDocumentStatus.REJECTED
    doc.rejection_reason = request.reason
    doc.verified_at = datetime.utcnow()
    doc.verified_by = current_user.id
    db.add(doc)

    # Update user KYC status to rejected
    user = db.get(User, doc.user_id)
    if user:
        user.kyc_status = KYCStatus.REJECTED
        user.kyc_rejection_reason = request.reason
        user.updated_at = datetime.utcnow()
        db.add(user)

    db.commit()
    db.refresh(doc)

    return {"status": "success", "message": "Document rejected", "reason": request.reason}
