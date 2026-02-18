from typing import Dict, Any, Optional, Protocol
from app.models.kyc import KYCDocumentType, KYCDocumentStatus
from app.models.user import User, KYCStatus
from app.core.config import settings
from sqlmodel import Session
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

kyc_service = KYCService()
