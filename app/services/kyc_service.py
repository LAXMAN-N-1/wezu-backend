from typing import Dict, Any, Optional, Protocol, List
from app.models.kyc import KYCDocumentType, KYCDocumentStatus
from app.models.user import User, KYCStatus
from app.core.config import settings
from app.core.logging import get_logger
from sqlmodel import Session, select, func
from datetime import datetime, UTC, timedelta

logger = get_logger(__name__)

class KYCProvider(Protocol):
    async def verify_aadhaar(self, aadhaar_number: str) -> Dict[str, Any]: ...
    async def verify_pan(self, pan_number: str) -> Dict[str, Any]: ...

class MockKYCProvider:
    """Mock provider for development/testing only."""
    async def verify_aadhaar(self, aadhaar_number: str) -> Dict[str, Any]:
        logger.info("kyc.mock_aadhaar_verify", aadhaar_prefix=aadhaar_number[:4])
        return {"success": True, "verification_id": f"mock_aadhaar_{aadhaar_number[:4]}", "status": "VERIFIED"}

    async def verify_pan(self, pan_number: str) -> Dict[str, Any]:
        logger.info("kyc.mock_pan_verify", pan_prefix=pan_number[:4])
        return {"success": True, "verification_id": f"mock_pan_{pan_number[:4]}", "status": "VERIFIED"}


class PendingReviewProvider:
    """Production fallback: marks documents for manual review instead of auto-verifying."""
    async def verify_aadhaar(self, aadhaar_number: str) -> Dict[str, Any]:
        logger.info("kyc.pending_aadhaar_review", aadhaar_prefix=aadhaar_number[:4])
        return {"success": True, "verification_id": None, "status": "PENDING_REVIEW"}

    async def verify_pan(self, pan_number: str) -> Dict[str, Any]:
        logger.info("kyc.pending_pan_review", pan_prefix=pan_number[:4])
        return {"success": True, "verification_id": None, "status": "PENDING_REVIEW"}


class KYCService:
    def __init__(self):
        if settings.ENVIRONMENT == "production":
            # Production: queue for manual review until real KYC API is integrated
            self.provider = PendingReviewProvider()
            logger.info("kyc.manual_review_mode_active")
        else:
            self.provider = MockKYCProvider()

        # ── Production safety guard ──────────────────────────────────────
        # MockKYCProvider auto-approves ALL documents.  It MUST NEVER be
        # the active provider in production, even if someone changes the
        # conditional above.  This is a belt-and-suspenders check.
        if settings.ENVIRONMENT == "production" and isinstance(self.provider, MockKYCProvider):
            raise RuntimeError(
                "FATAL: MockKYCProvider is active in production. "
                "This would auto-approve all KYC submissions. "
                "Use PendingReviewProvider or a real KYC integration."
            )

    async def verify_aadhaar(self, db: Session, user: User, aadhaar_number: str) -> Dict[str, Any]:
        """Verify Aadhaar and update user status based on provider response."""
        result = await self.provider.verify_aadhaar(aadhaar_number)

        if result.get("success"):
            status_map = {
                "VERIFIED": KYCStatus.APPROVED,
                "PENDING_REVIEW": KYCStatus.PENDING,
            }
            user.kyc_status = status_map.get(result.get("status"), KYCStatus.PENDING)
            db.add(user)
            db.commit()

        return result

    async def verify_pan(self, db: Session, user: User, pan_number: str) -> Dict[str, Any]:
        """
        Verify PAN and update user status to VERIFIED if all checks pass.
        """
        result = await self.provider.verify_pan(pan_number)
        
        if result.get("success"):
            user.kyc_status = KYCStatus.APPROVED
            db.add(user)
            db.commit()
            
        return result

    @staticmethod
    async def process_video_kyc(db: Session, user: User, recording_url: str) -> Dict[str, Any]:
        """Process video KYC. Queues for manual review in production."""
        if settings.ENVIRONMENT == "production":
            logger.info("kyc.video_queued_manual_review", user_id=user.id)
            user.kyc_status = KYCStatus.PENDING
            db.add(user)
            db.commit()
            return {"liveness_score": None, "status": "PENDING_REVIEW"}
        # Dev/test: auto-approve with synthetic score (never reaches production
        # due to the branch above).
        logger.info("kyc.video_dev_auto_approve", user_id=user.id)
        return {"liveness_score": 0.98, "status": "APPROVED", "_dev_mode": True}

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
        """Process utility bill for address verification."""
        logger.info("kyc.utility_bill_processing", user_id=user_id, file_path=file_path)

        from app.models.kyc import KYCRecord
        record = db.exec(select(KYCRecord).where(KYCRecord.user_id == user_id)).first()
        if not record:
            record = KYCRecord(user_id=user_id)

        record.utility_bill_url = file_path
        record.updated_at = datetime.now(UTC)
        db.add(record)
        db.commit()

        if settings.ENVIRONMENT == "production":
            # In production: queue for manual review or OCR service
            return {"success": True, "extracted_address": None, "match_confidence": None, "status": "PENDING_REVIEW"}

        # Dev/test: return synthetic data (never reaches production)
        logger.info("kyc.utility_bill_dev_synthetic", user_id=user_id)
        return {"success": True, "extracted_address": "Dev Test Address 123", "match_confidence": 0.95, "_dev_mode": True}

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
        
        today = datetime.now(UTC).date()
        
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

    # ── P1-A-6: Document-level approve / reject ──────────────────────────

    @staticmethod
    def approve_document(db: Session, document_id: int, reviewer_id: int | None = None):
        """Set KYCDocument status to verified with audit trail."""
        from app.models.kyc import KYCDocument, KYCDocumentStatus

        doc = db.get(KYCDocument, document_id)
        if not doc:
            return None
        doc.status = KYCDocumentStatus.VERIFIED
        doc.verified_at = datetime.now(UTC)
        if reviewer_id is not None:
            doc.verified_by = reviewer_id
        doc.rejection_reason = None
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def reject_document(db: Session, document_id: int, reason: str, reviewer_id: int | None = None):
        """Set KYCDocument status to rejected with reason."""
        from app.models.kyc import KYCDocument, KYCDocumentStatus

        doc = db.get(KYCDocument, document_id)
        if not doc:
            return None
        doc.status = KYCDocumentStatus.REJECTED
        doc.rejection_reason = reason
        doc.verified_at = datetime.now(UTC)
        if reviewer_id is not None:
            doc.verified_by = reviewer_id
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

kyc_service = KYCService()
