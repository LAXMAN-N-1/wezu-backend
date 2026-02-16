from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlmodel import Session, select
from app.db.session import get_session
from app.models.user import User
from app.models.kyc import KYCRecord
from app.api import deps
import shutil
import os
from datetime import datetime
from typing import Optional

router = APIRouter()

@router.get("/status")
async def get_kyc_status(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Get current user's KYC status"""
    # Fetch KYC record
    record = db.exec(select(KYCRecord).where(KYCRecord.user_id == current_user.id)).first()
    
    # Compatibility with remote KYCStatusResponse
    return {
        "kyc_status": current_user.kyc_status,
        "record": record,
        "rejection_reason": current_user.kyc_rejection_reason,
        "missing_docs": [] # Logic to calculate missing docs if needed
    }

@router.post("/submit")
async def submit_kyc_document(
    document_type: str = Form(...), # aadhaar_front, aadhaar_back, pan_card, utility_bill
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Upload KYC document"""
    # 1. Validate
    valid_types = ["aadhaar_front", "aadhaar_back", "pan_card", "utility_bill"]
    if document_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid document type")

    # 2. Save File
    upload_dir = f"uploads/kyc/{current_user.id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = f"{upload_dir}/{document_type}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 3. Update/Create KYC Record
    record = db.exec(select(KYCRecord).where(KYCRecord.user_id == current_user.id)).first()
    if not record:
        record = KYCRecord(user_id=current_user.id)
        db.add(record)
        
    # Update specific field based on type
    if document_type == "aadhaar_front":
        record.aadhaar_front_url = file_path
    elif document_type == "aadhaar_back":
        record.aadhaar_back_url = file_path
    elif document_type == "pan_card":
        record.pan_card_url = file_path
    elif document_type == "utility_bill":
        record.utility_bill_url = file_path
        
    record.updated_at = datetime.utcnow()
    # If all docs present, update status to submitted?
    # Logic simplified for now
    if current_user.kyc_status == "verified":
         pass # Don't downgrade if verified?
    else:
         current_user.kyc_status = "submitted"
         record.status = "submitted"
         
    db.add(record)
    db.add(current_user)
    db.commit()
    return {"message": "Document uploaded successfully", "file_path": file_path}

@router.post("/aadhaar-verify")
async def verify_aadhaar(
    aadhaar_number: str = Form(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """
    Verify Aadhaar Number (Mock Integration)
    In real world: Call API (e.g. Karza/Signzy), verify OTP sent to mobile linked to Aadhaar
    """
    # Mock Validation
    if len(aadhaar_number) != 12 or not aadhaar_number.isdigit():
        raise HTTPException(status_code=400, detail="Invalid Aadhaar Number format")
        
    # Store Encrypted (Mock encryption)
    encrypted_val = f"ENC_{aadhaar_number}"
    
    record = db.exec(select(KYCRecord).where(KYCRecord.user_id == current_user.id)).first()
    if not record:
        record = KYCRecord(user_id=current_user.id)
    
    record.aadhaar_number_enc = encrypted_val
    db.add(record)
    db.commit()
    
    return {"status": "verified", "message": "Aadhaar verified successfully"}

@router.post("/pan-verify")
async def verify_pan(
    pan_number: str = Form(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """
    Verify PAN Number (Mock Integration)
    """
    # Mock Validation
    if len(pan_number) != 10:
        raise HTTPException(status_code=400, detail="Invalid PAN Number format")
        
    encrypted_val = f"ENC_{pan_number}"
    
    record = db.exec(select(KYCRecord).where(KYCRecord.user_id == current_user.id)).first()
    if not record:
        record = KYCRecord(user_id=current_user.id)
    
    record.pan_number_enc = encrypted_val
    db.add(record)
    db.commit()
    
    return {"status": "verified", "message": "PAN verified successfully"}

@router.post("/video-kyc")
async def upload_video_kyc(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """
    Upload Video KYC and Perform Liveness Check
    """
    # 1. Save Video
    upload_dir = f"uploads/kyc/{current_user.id}"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/video_kyc_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. Mock Liveness Check
    liveness_score = 0.98 # high score
    
    record = db.exec(select(KYCRecord).where(KYCRecord.user_id == current_user.id)).first()
    if not record:
        record = KYCRecord(user_id=current_user.id)
        
    record.video_kyc_url = file_path
    record.liveness_score = liveness_score
    
    db.add(record)
    db.commit()
    
    return {"liveness_score": liveness_score, "status": "success"}

# Remote Video KYC Service Endpoints
@router.post("/me/kyc/video-kyc/request")
def request_video_kyc(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Request a live video KYC session.
    """
    from app.services.video_kyc_service import VideoKYCService
    session = VideoKYCService.schedule_session(current_user.id, datetime.utcnow(), db=db)
    return session

@router.post("/me/kyc/resubmit")
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
    
    current_user.kyc_status = "pending_verification"
    current_user.kyc_rejection_reason = None
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return current_user
