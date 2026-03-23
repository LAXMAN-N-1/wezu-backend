import os
from datetime import datetime
from fastapi import UploadFile
from sqlmodel import Session, select
from typing import List, Optional

from app.models.dealer_kyc import DealerKYCApplication, KYCStateConfig, KYCStateTransition

class DealerKYCService:
    @staticmethod
    def _log_transition(db: Session, app_id: int, from_state: str, to_state: str, user_id: int, reason: Optional[str] = None):
        transition = KYCStateTransition(
            application_id=app_id,
            from_state=from_state,
            to_state=to_state,
            changed_by_user_id=user_id,
            reason=reason
        )
        db.add(transition)
        db.commit()

    @staticmethod
    async def _mock_s3_upload(file: UploadFile, prefix: str) -> str:
        # Mocking S3 Upload and Encryption Check
        allowed_types = ["application/pdf", "image/jpeg", "image/jpg"]
        
        # We need to correctly read the content type
        if file.content_type not in allowed_types and not file.filename.lower().endswith(('.pdf', '.jpg', '.jpeg')):
            raise ValueError(f"Invalid file type for {file.filename}. Only PDF and JPG are allowed.")
            
        return f"s3://encrypted-bucket/kyc/{prefix}_{file.filename}"

    @staticmethod
    async def submit_documents(
        db: Session, 
        user_id: int, 
        company_name: str, 
        pan_number: str, 
        gst_number: str, 
        bank_details_json: str,
        pan_file: UploadFile,
        gst_file: UploadFile,
        reg_cert: UploadFile
    ) -> DealerKYCApplication:
        existing = db.exec(select(DealerKYCApplication).where(DealerKYCApplication.user_id == user_id)).first()
        if existing and existing.application_state not in [KYCStateConfig.REJECTED, KYCStateConfig.REGISTRATION]:
            raise ValueError("KYC application already in progress.")
            
        pan_url = await DealerKYCService._mock_s3_upload(pan_file, f"{user_id}_pan")
        gst_url = await DealerKYCService._mock_s3_upload(gst_file, f"{user_id}_gst")
        reg_url = await DealerKYCService._mock_s3_upload(reg_cert, f"{user_id}_reg")
        
        if existing:
            # Update existing
            existing.company_name = company_name
            existing.pan_number = pan_number
            existing.gst_number = gst_number
            existing.bank_details_json = bank_details_json
            existing.pan_doc_url = pan_url
            existing.gst_doc_url = gst_url
            existing.reg_cert_url = reg_url
            
            from_state = existing.application_state.value
            existing.application_state = KYCStateConfig.DOC_SUBMITTED
            existing.updated_at = datetime.utcnow()
            
            db.add(existing)
            db.commit()
            db.refresh(existing)
            
            DealerKYCService._log_transition(db, existing.id, from_state, KYCStateConfig.DOC_SUBMITTED.value, user_id, "Documents re-submitted")
            return existing
            
        # Create new
        app = DealerKYCApplication(
            user_id=user_id,
            company_name=company_name,
            pan_number=pan_number,
            gst_number=gst_number,
            bank_details_json=bank_details_json,
            pan_doc_url=pan_url,
            gst_doc_url=gst_url,
            reg_cert_url=reg_url,
            application_state=KYCStateConfig.DOC_SUBMITTED
        )
        db.add(app)
        db.commit()
        db.refresh(app)
        
        DealerKYCService._log_transition(db, app.id, KYCStateConfig.REGISTRATION.value, KYCStateConfig.DOC_SUBMITTED.value, user_id, "Initial form sumbitted")
        
        return app

    @staticmethod
    def run_auto_checks(db: Session, user_id: int) -> DealerKYCApplication:
        app = db.exec(select(DealerKYCApplication).where(DealerKYCApplication.user_id == user_id)).first()
        if not app:
            raise ValueError("No KYC application found.")
            
        if app.application_state != KYCStateConfig.DOC_SUBMITTED:
            raise ValueError(f"Cannot run auto-checks from state {app.application_state}")
            
        # Transition to AUTO_CHECKS
        app.application_state = KYCStateConfig.AUTO_CHECKS
        db.add(app)
        db.commit()
        db.refresh(app)
        DealerKYCService._log_transition(db, app.id, KYCStateConfig.DOC_SUBMITTED.value, KYCStateConfig.AUTO_CHECKS.value, user_id, "Started auto checks")
        
        # MOCK API CHECKS (< 30 seconds)
        # We will use the pan_number as a mock controller for testing
        if app.pan_number == "FAILED_PAN":
            app.application_state = KYCStateConfig.REJECTED
            app.rejection_reason = "Automated checks failed: Invalid PAN."
            db.add(app)
            db.commit()
            db.refresh(app)
            DealerKYCService._log_transition(db, app.id, KYCStateConfig.AUTO_CHECKS.value, KYCStateConfig.REJECTED.value, user_id, "Automated checks failed")
            return app

        # Pass transition
        app.application_state = KYCStateConfig.MANUAL_REVIEW
        db.add(app)
        db.commit()
        db.refresh(app)
        DealerKYCService._log_transition(db, app.id, KYCStateConfig.AUTO_CHECKS.value, KYCStateConfig.MANUAL_REVIEW.value, user_id, "Automated checks passed")
        
        return app

    @staticmethod
    def manual_review(db: Session, app_id: int, admin_user_id: int, approve: bool, comments: str) -> DealerKYCApplication:
        app = db.get(DealerKYCApplication, app_id)
        if not app:
            raise ValueError("No such application.")
            
        if app.application_state != KYCStateConfig.MANUAL_REVIEW:
             raise ValueError(f"Application is in {app.application_state}, not MANUAL_REVIEW.")
             
        app.admin_comments = comments
        from_state = app.application_state.value
        
        if approve:
            app.application_state = KYCStateConfig.APPROVED
        else:
            app.application_state = KYCStateConfig.REJECTED
            app.rejection_reason = comments
            
        db.add(app)
        db.commit()
        db.refresh(app)
        
        DealerKYCService._log_transition(db, app.id, from_state, app.application_state.value, admin_user_id, f"Admin Review: {'Approved' if approve else 'Rejected'}")
        return app
        
    @staticmethod
    def activate_dealer(db: Session, app_id: int, admin_user_id: int) -> DealerKYCApplication:
        app = db.get(DealerKYCApplication, app_id)
        if not app:
            raise ValueError("No such application.")
            
        if app.application_state != KYCStateConfig.APPROVED:
             raise ValueError(f"Application is in {app.application_state}, not APPROVED.")
             
        # In a real app, this might trigger creating a DealerProfile, sending emails, etc.
        app.application_state = KYCStateConfig.ACTIVE
        db.add(app)
        db.commit()
        db.refresh(app)
        
        DealerKYCService._log_transition(db, app.id, KYCStateConfig.APPROVED.value, KYCStateConfig.ACTIVE.value, admin_user_id, "Dealer Activated")
        return app

