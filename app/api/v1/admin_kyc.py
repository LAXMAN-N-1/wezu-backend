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

from datetime import datetime, UTC
from app.models.user import User, KYCStatus
from app.schemas.kyc import KYCDocumentResponse, KYCQueueItem, KYCQueueResponse, KYCVerifyRequest, KYCDashboardResponse
from app.schemas.kyc_admin import KYCRejectRequest
from app.services.email_service import EmailService

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
    query = select(User).where(User.kyc_status == KYCStatus.PENDING)
    
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

    return KYCQueueResponse(
        items=items,
        total=total,
        page=page,
        size=size
    )

@router.post("/{user_id}/verify", response_model=Any)
def verify_kyc_submission(
    user_id: int,
    request: KYCVerifyRequest,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Approve or reject a KYC submission.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update User Status
    if request.decision == "approved":
        user.kyc_status = KYCStatus.APPROVED
    elif request.decision == "rejected":
        user.kyc_status = KYCStatus.REJECTED
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")
    
    db.add(user)
    
    # Process Documents
    docs = db.exec(select(KYCDocument).where(KYCDocument.user_id == user_id)).all()
    doc_map = {d.id: d for d in docs}
    
    if request.rejection_reasons:
        for doc_id, reason in request.rejection_reasons.items():
            if doc_id in doc_map:
                doc = doc_map[doc_id]
                doc.status = "rejected"
                doc.verification_response = reason
                db.add(doc)
    
    # If approved, mark all non-rejected docs as verified
    if request.decision == "approved":
        for doc in docs:
            if doc.status != "rejected":
                doc.status = "verified"
                db.add(doc)
                
    db.commit()
    db.refresh(user)
    
    # Send Notification (Email)
    status_text = "Approved" if user.kyc_status == KYCStatus.APPROVED else "Rejected"
    email_content = f"""
        <h3>KYC Status Update</h3>
        <p>Your Recent KYC submission has been <b>{status_text}</b>.</p>
    """
    if user.kyc_status == KYCStatus.REJECTED:
        email_content += f"<p>Reason: Please check your portal for issues with your documents.</p>"
        
    EmailService.send_email(
        to_email=user.email,
        subject=f"Wezu Energy - KYC {status_text}",
        content=email_content
    )
    return {"status": "success", "user_status": user.kyc_status}

@router.get("/documents", response_model=dict)
def list_kyc_documents(
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: List all KYC documents with user info."""
    query = select(KYCDocument, User).join(User, KYCDocument.user_id == User.id)
    
    if status:
        query = query.where(KYCDocument.status == status)
        
    query = query.order_by(KYCDocument.uploaded_at.desc())
        
    total_count = db.exec(select(func.count()).select_from(query.subquery())).one()
    results = db.exec(query.offset(skip).limit(limit)).all()
    
    docs_list = []
    for doc, user in results:
        docs_list.append({
            "id": doc.id,
            "user_id": user.id,
            "user_name": user.full_name or "Unknown",
            "user_email": user.email or "",
            "user_phone": user.phone_number,
            "document_type": getattr(doc, "document_type", "Unknown"),
            "document_number": getattr(doc, "document_number", None),
            "file_url": doc.file_url,
            "status": doc.status,
            "rejection_reason": getattr(doc, "rejection_reason", getattr(doc, "verification_response", None)),
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "verified_at": getattr(doc, "verified_at", None),
            "verified_by": getattr(doc, "verified_by", None),
        })
        
    return {
        "documents": docs_list,
        "total_count": total_count
    }

@router.get("/stats", response_model=dict)
def get_kyc_stats(
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: KYC Global Stats"""
    docs = db.exec(select(KYCDocument.status)).all()
    
    total = len(docs)
    pending = sum(1 for d in docs if d == "PENDING")
    verified = sum(1 for d in docs if d == "VERIFIED")
    rejected = sum(1 for d in docs if d == "REJECTED")
    
    pending_users = db.exec(select(func.count(User.id)).where(User.kyc_status == "PENDING")).one()
    
    return {
        "total_documents": total,
        "total_pending": pending,
        "total_verified": verified,
        "total_rejected": rejected,
        "pending_users": pending_users
    }

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

@router.post("/{user_id}/reject", response_model=Any)
def reject_kyc_submission(
    user_id: int,
    request: KYCRejectRequest,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Reject a KYC submission with a mandatory reason.
    """
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update User Status and Reason
    user.kyc_status = KYCStatus.REJECTED
    user.kyc_rejection_reason = request.reason
    db.add(user)
    
    # Process Documents (Optional granular rejection)
    if request.rejection_reasons:
        # Re-fetch docs to be sure
        docs = db.exec(select(KYCDocument).where(KYCDocument.user_id == user_id)).all()
        doc_map = {d.id: d for d in docs}
        
        for doc_id, reason in request.rejection_reasons.items():
            if doc_id in doc_map:
                doc = doc_map[doc_id]
                doc.status = "rejected"
                doc.verification_response = reason
                db.add(doc)
                
    db.commit()
    db.refresh(user)
    
    # Send Notification (Email)
    email_content = f"""
        <h3>KYC Application Rejected</h3>
        <p>Unfortunately, your KYC application was rejected for the following reason:</p>
        <p><b>{request.reason}</b></p>
        <p>Please log in to the portal, update your documents, and submit again.</p>
    """
    EmailService.send_email(
        to_email=user.email,
        subject="Wezu Energy - KYC Rejected",
        content=email_content
    )
    
    return {"status": "success", "user_status": user.kyc_status, "reason": user.kyc_rejection_reason}

from app.schemas.video_kyc import VideoKYCCompleteRequest
from app.services.video_kyc_service import VideoKYCService

@router.post("/video-kyc/{session_id}/complete", response_model=Any)
def complete_video_kyc(
    session_id: int,
    request: VideoKYCCompleteRequest,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Mark a Video KYC session as complete/verified.
    """
    # 1. Update Session
    status = "completed" if request.verification_result == "approved" else "rejected"
    vks = VideoKYCService.update_status(
        session_id=session_id, 
        status=status, 
        recording_url=request.recording_link,
        notes=request.agent_notes,
        db=db
    )
    
    if not vks:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 2. Update User KYC Status
    user = db.get(User, vks.user_id)
    if user:
        if request.verification_result == "approved":
            user.kyc_status = KYCStatus.APPROVED
            # user.kyc_video_url = request.recording_link 
        elif request.verification_result == "rejected":
            user.kyc_status = KYCStatus.REJECTED
            if request.agent_notes:
                user.kyc_rejection_reason = request.agent_notes
        
        db.add(user)
        db.commit()
            
    return {"status": "success", "session_status": vks.status}

@router.get("/dashboard", response_model=KYCDashboardResponse)
def get_kyc_admin_dashboard(
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Admin: KYC status counts (pending, approved, rejected today)"""
    return KYCService.get_admin_dashboard_stats(db)

@router.put("/{user_id}/approve")
def approve_user_kyc(
    user_id: int,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Admin: approve a user's KYC submission"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.kyc_status = KYCStatus.APPROVED
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    return {"message": "User KYC approved successfully"}

@router.put("/{user_id}/reject")
def reject_user_kyc(
    user_id: int,
    request: KYCRejectRequest,
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
):
    """Admin: reject KYC with mandatory reason code and notes"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.kyc_status = KYCStatus.REJECTED
    user.kyc_rejection_reason = request.reason
    user.updated_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    return {"message": "User KYC rejected successfully", "reason": request.reason}
