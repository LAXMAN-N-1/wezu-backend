from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlmodel import Session
from typing import List

from app.api import deps
from app.models.user import User
from app.models.address import Address
from app.models.kyc import KYCDocument
from app.schemas.user import UserResponse, UserUpdate, AddressCreate, AddressResponse, AddressUpdate
from app.schemas.kyc import KYCDocumentResponse, KYCStatusResponse, KYCSubmitRequest, KYCDocumentUpload
from app.services.user_service import UserService
from app.services.kyc_service import KYCService

router = APIRouter()

@router.get("/me/kyc", response_model=KYCStatusResponse)
async def get_kyc_status(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    docs = KYCService.get_documents(db, current_user.id)
    return KYCStatusResponse(
        kyc_status=current_user.kyc_status,
        documents=docs,
        rejection_reason=current_user.kyc_rejection_reason
    )

@router.post("/me/kyc/documents", response_model=KYCDocumentResponse)
async def upload_kyc_document(
    document_type: str,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    # Process file upload here (save to disk or cloud)
    # For now, mock URL
    file_url = f"/uploads/kyc/{current_user.id}/{file.filename}"
    
    doc_in = KYCDocumentUpload(document_type=document_type)
    doc = KYCService.upload_document(db, current_user.id, doc_in, file_url)
    return doc

@router.post("/me/kyc/submit", response_model=UserResponse)
async def submit_kyc(
    kyc_data: KYCSubmitRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    user = KYCService.submit_kyc(db, current_user.id, kyc_data.aadhaar_number, kyc_data.pan_number)
    return user

from app.services.video_kyc_service import VideoKYCService
from app.models.video_kyc import VideoKYCSession
from datetime import datetime
from pydantic import BaseModel

class VideoKYCSchedule(BaseModel):
    scheduled_at: datetime

@router.post("/me/kyc/video/schedule", response_model=VideoKYCSession)
def schedule_video_kyc(
    req: VideoKYCSchedule,
    current_user: User = Depends(deps.get_current_user),
):
    # Should use DB from deps but Service creates its own session (bad practice mix, but I followed service pattern earlier)
    # Actually VideoKYCService uses `with Session(engine) as session`.
    # I should stick to that or refactor. Sticking to it for consistency in this turn.
    return VideoKYCService.schedule_session(current_user.id, req.scheduled_at)

    # Find scheduled session
    # For now, just create one immediately if not exists?
    return VideoKYCService.schedule_session(current_user.id, datetime.utcnow())

@router.post("/me/kyc/video-kyc/request", response_model=VideoKYCSession)
def request_video_kyc(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Request a live video KYC session.
    """
    # Create an immediate session (or schedule for "now")
    session = VideoKYCService.schedule_session(current_user.id, datetime.utcnow(), db=db)
    return session

@router.post("/me/kyc/resubmit", response_model=UserResponse)
async def resubmit_kyc(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Resubmit KYC after rejection. Resets status to pending.
    """
    if current_user.kyc_status != "rejected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Can only resubmit if current status is rejected"
        )
    
    # Reset status
    current_user.kyc_status = "pending_verification"
    # Keep the rejection reason for history? Or clear it? 
    # Usually better to clear it to indicate a fresh start, or move to history table.
    # For this simple implementation, we can clear it or leave it. 
    # Let's clear it to show "clean slate" on UI.
    current_user.kyc_rejection_reason = None
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return current_user
