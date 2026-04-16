import os
from datetime import datetime, UTC
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
    async def _upload_to_s3(file: UploadFile, prefix: str) -> str:
        from app.core.config import settings
        import uuid
        import boto3
        import logging
        import os
        
        logger = logging.getLogger("wezu_storage")
        allowed_types = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]
        
        if file.content_type not in allowed_types and not file.filename.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
            raise ValueError(f"Invalid file type for {file.filename}. Only PDF and images are allowed.")
            
        ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
        unique_filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
        
        bucket = getattr(settings, "AWS_BUCKET_NAME", None)
        is_test_env = getattr(settings, "ENVIRONMENT", "development") == "test"
        
        if not is_test_env and bucket and settings.AWS_ACCESS_KEY_ID:
            try:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION or 'ap-south-1'
                )
                
                content = await file.read()
                s3_client.put_object(
                    Bucket=bucket,
                    Key=f"kyc/{unique_filename}",
                    Body=content,
                    ContentType=file.content_type
                )
                
                domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
                if domain:
                    return f"https://{domain}/kyc/{unique_filename}"
                return f"https://{bucket}.s3.{settings.AWS_REGION or 'ap-south-1'}.amazonaws.com/kyc/{unique_filename}"
            except Exception as e:
                logger.error(f"S3_UPLOAD_ERROR: Failed to upload {file.filename}: {e}", exc_info=True)
                raise ValueError(f"Failed to securely store document: {e}")
        else:
            # Fallback to local storage to prevent data loss when AWS is not configured
            logger.warning("STORAGE_WARNING: S3 not configured. Using local fallback.")
            upload_dir = getattr(settings, "LOCAL_STORAGE_PATH", "/tmp/wezu_uploads")
            os.makedirs(f"{upload_dir}/kyc", exist_ok=True)
            
            file_path = f"{upload_dir}/kyc/{unique_filename}"
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
                
            return f"file://{file_path}"

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
            
        pan_url = await DealerKYCService._upload_to_s3(pan_file, f"{user_id}_pan")
        gst_url = await DealerKYCService._upload_to_s3(gst_file, f"{user_id}_gst")
        reg_url = await DealerKYCService._upload_to_s3(reg_cert, f"{user_id}_reg")
        
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
            existing.updated_at = datetime.now(UTC)
            
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

