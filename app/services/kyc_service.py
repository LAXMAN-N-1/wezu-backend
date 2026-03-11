from typing import Dict, Any, Optional, Protocol, List
from app.models.kyc import KYCDocumentType, KYCDocumentStatus
from app.models.user import User, KYCStatus
from app.core.config import settings
from sqlmodel import Session, select, func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class KYCProvider(Protocol):
    async def verify_aadhaar(self, aadhaar_number: str) -> Dict[str, Any]: ...
    async def verify_pan(self, pan_number: str) -> Dict[str, Any]: ...

class MockKYCProvider:
    async def verify_aadhaar(self, aadhaar_number: str) -> Dict[str, Any]:
        return {"success": True, "verification_id": "mock_aadhaar_v1", "status": "VERIFIED"}
        
    async def verify_pan(self, pan_number: str) -> Dict[str, Any]:
        return {"success": True, "verification_id": "mock_pan_v1", "status": "VERIFIED"}

class KYCService:
    def __init__(self):
        # In a real app, we'd pick the provider based on settings.ENVIRONMENT or a config flag
        if settings.ENVIRONMENT == "production":
            # self.provider = ProductionKYCProvider()
            self.provider = MockKYCProvider() # Still mock until keys are provided
        else:
            self.provider = MockKYCProvider()

    async def verify_aadhaar(self, db: Session, user: User, aadhaar_number: str) -> Dict[str, Any]:
        """
        Verify Aadhaar and update user status.
        """
        result = await self.provider.verify_aadhaar(aadhaar_number)
        
        if result.get("success"):
            # Update Document Status in DB (Assuming document recording logic exists elsewhere or here)
            user.kyc_status = KYCStatus.PENDING 
            db.add(user)
            db.commit()
            
        return result

    async def verify_pan(self, db: Session, user: User, pan_number: str) -> Dict[str, Any]:
        """
        Verify PAN and update user status to VERIFIED if all checks pass.
        """
        result = await self.provider.verify_pan(pan_number)
        
        if result.get("success"):
            user.kyc_status = KYCStatus.VERIFIED
            db.add(user)
            db.commit()
            
        return result

    @staticmethod
    async def process_video_kyc(db: Session, user: User, recording_url: str) -> Dict[str, Any]:
        return {"liveness_score": 0.98, "status": "APPROVED"}

    @staticmethod
    def get_rejection_reasons() -> List[Dict[str, str]]:
        """Standardized rejection codes per Phase 1 SRS"""
        return [
            {"code": "DOC_BLURRY", "description": "Document image is not clear or blurry"},
            {"code": "NAME_MISMATCH", "description": "Name on document does not match profile"},
            {"code": "EXP_DOC", "description": "Document has expired"},
            {"code": "INCOMPLETE_DOC", "description": "Mandatory parts of document are missing (e.g. back side)"},
            {"code": "INVALID_ADDRESS", "description": "Utility bill does not confirm a valid service address"},
            {"code": "PHOTO_MISMATCH", "description": "Face in video KYC does not match ID document"},
            {"code": "POSSIBLE_FRAUD", "description": "Suspicious activity detected during verification"}
        ]

    @staticmethod
    async def verify_utility_bill(db: Session, user_id: int, file_path: str) -> Dict[str, Any]:
        """Mock OCR and validation for Address Proof"""
        # In production: Trigger AWS Textract or similar
        logger.info(f"Processing utility bill for user {user_id}: {file_path}")
        
        from app.models.kyc import KYCRecord
        record = db.exec(select(KYCRecord).where(KYCRecord.user_id == user_id)).first()
        if not record:
            record = KYCRecord(user_id=user_id)
        
        record.utility_bill_url = file_path
        record.updated_at = datetime.utcnow()
        db.add(record)
        db.commit()
        
        return {"success": True, "extracted_address": "Mock Extracted Address 123", "match_confidence": 0.95}

    @staticmethod
    def resubmit_kyc(db: Session, user_id: int):
        """Reset KYC status and clear document records for fresh start"""
        from app.models.user import User
        from app.models.kyc import KYCRecord, KYCDocument
        
        user = db.get(User, user_id)
        if not user:
            return False
            
        user.kyc_status = KYCStatus.PENDING
        user.kyc_rejection_reason = None
        db.add(user)
        
        # Clear KYCRecord urls
        record = db.exec(select(KYCRecord).where(KYCRecord.user_id == user_id)).first()
        if record:
            record.aadhaar_front_url = None
            record.aadhaar_back_url = None
            record.pan_card_url = None
            record.video_kyc_url = None
            record.utility_bill_url = None
            record.status = KYCStatus.PENDING
            db.add(record)
            
        # Optional: Delete granular docs or mark as removed
        docs = db.exec(select(KYCDocument).where(KYCDocument.user_id == user_id)).all()
        for doc in docs:
            db.delete(doc)
            
        db.commit()
        return True

    @staticmethod
    def get_admin_dashboard_stats(db: Session) -> Dict[str, Any]:
        """Fetch KYC status counts and trends"""
        from app.models.user import User
        from sqlalchemy import Date, cast
        
        today = datetime.utcnow().date()
        
        pending_count = db.exec(select(func.count(User.id)).where(User.kyc_status == KYCStatus.PENDING)).one()
        
        # Approved/Rejected today (Simplified: check updated_at for users in that status)
        # Note: In a real DB we'd use a KycVerificationLog table for precision
        approved_today = db.exec(select(func.count(User.id)).where(
            User.kyc_status == KYCStatus.APPROVED, 
            cast(User.updated_at, Date) == today
        )).one()
        
        rejected_today = db.exec(select(func.count(User.id)).where(
            User.kyc_status == KYCStatus.REJECTED,
            cast(User.updated_at, Date) == today
        )).one()
        
        return {
            "total_pending": pending_count,
            "total_approved_today": approved_today,
            "total_rejected_today": rejected_today,
            "submission_trend": {} # Could aggregate over last 7 days
        }

kyc_service = KYCService()
