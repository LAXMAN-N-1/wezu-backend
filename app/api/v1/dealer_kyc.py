from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User, UserType
from app.models.roles import RoleEnum
from app.models.dealer_kyc import DealerKYCApplication, KYCStateConfig, KYCStateTransition
from app.schemas.common import DataResponse
from app.services.dealer_kyc_service import DealerKYCService
from pydantic import BaseModel

router = APIRouter()

class AdminReview(BaseModel):
    action: str # "approve" or "reject"
    comments: str

@router.post("/kyc/documents", response_model=DataResponse[DealerKYCApplication])
async def submit_documents(
    company_name: str = Form(...),
    pan_number: str = Form(...),
    gst_number: str = Form(...),
    bank_details_json: str = Form(...),
    pan_doc_file: UploadFile = File(...),
    gst_doc_file: UploadFile = File(...),
    reg_cert_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Submits the initial dealer documents and transitions to DOC_SUBMITTED
    """
    try:
        app = await DealerKYCService.submit_documents(
            db=db,
            user_id=current_user.id,
            company_name=company_name,
            pan_number=pan_number,
            gst_number=gst_number,
            bank_details_json=bank_details_json,
            pan_file=pan_doc_file,
            gst_file=gst_doc_file,
            reg_cert=reg_cert_file
        )
        return DataResponse(data=app)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/kyc/trigger-auto-checks", response_model=DataResponse[DealerKYCApplication])
def trigger_auto_checks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Dealer triggers the automated checks API phase.
    """
    try:
        app = DealerKYCService.run_auto_checks(db, current_user.id)
        return DataResponse(data=app)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/admin/dealers/pending", response_model=DataResponse[List[DealerKYCApplication]])
def get_pending_dealers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Admin checks manual review required items.
    """
    if current_user.user_type != UserType.ADMIN:
         raise HTTPException(status_code=403, detail="Admin only")
         
    dealers = db.exec(
        select(DealerKYCApplication).where(DealerKYCApplication.application_state == KYCStateConfig.MANUAL_REVIEW)
    ).all()
    return DataResponse(data=dealers)

@router.post("/admin/dealers/{application_id}/review", response_model=DataResponse[DealerKYCApplication])
def review_dealer(
    application_id: int,
    review: AdminReview,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    if current_user.user_type != UserType.ADMIN:
         raise HTTPException(status_code=403, detail="Admin only")
        
    try:
        if review.action == "approve":
            app = DealerKYCService.manual_review(db, application_id, current_user.id, True, review.comments)
            # You can chain this for the sake of the exercise
            app = DealerKYCService.activate_dealer(db, application_id, current_user.id)
            return DataResponse(data=app)
        else:
            app = DealerKYCService.manual_review(db, application_id, current_user.id, False, review.comments)
            return DataResponse(data=app)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/my-status", response_model=DataResponse[Optional[DealerKYCApplication]])
def get_my_kyc_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Dealer checks their own KYC application status.
    """
    app = db.exec(
        select(DealerKYCApplication).where(DealerKYCApplication.user_id == current_user.id)
    ).first()
    return DataResponse(data=app)
