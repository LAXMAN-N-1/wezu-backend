from sqlmodel import Session, select
from app.models.kyc import KYCDocument, KYCRequest
from app.models.user import User
from app.schemas.kyc import KYCDocumentUpload
from typing import Optional, List
from datetime import datetime

class KYCService:
    @staticmethod
    def upload_document(db: Session, user_id: int, doc_in: KYCDocumentUpload, file_url: str) -> KYCDocument:
        db_doc = KYCDocument(
            user_id=user_id,
            document_type=doc_in.document_type,
            document_number=doc_in.document_number,
            file_url=file_url,
            status="pending"
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        return db_doc

    @staticmethod
    def get_documents(db: Session, user_id: int) -> List[KYCDocument]:
        statement = select(KYCDocument).where(KYCDocument.user_id == user_id)
        return db.exec(statement).all()

    @staticmethod
    def submit_kyc(db: Session, user_id: int, aadhar: Optional[str], pan: Optional[str]) -> User:
        user = db.get(User, user_id)
        if not user:
            return None
            
        if aadhar:
            user.aadhaar_number = aadhar
        if pan:
            user.pan_number = pan
            
        user.kyc_status = "pending_verification"
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
