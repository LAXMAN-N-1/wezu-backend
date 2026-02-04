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
    @staticmethod
    def approve_document(db: Session, doc_id: int) -> Optional[KYCDocument]:
        doc = db.get(KYCDocument, doc_id)
        if not doc:
            return None
        
        doc.status = "verified"
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        # Check if all required documents are now verified to finalize user KYC
        KYCService.finalize_kyc(db, doc.user_id)
        return doc

    @staticmethod
    def reject_document(db: Session, doc_id: int, reason: str) -> Optional[KYCDocument]:
        doc = db.get(KYCDocument, doc_id)
        if not doc:
            return None
        
        doc.status = "rejected"
        doc.verification_response = reason
        db.add(doc)
        
        # Update user status back to pending or rejected
        user = db.get(User, doc.user_id)
        if user:
            user.kyc_status = "rejected"
            db.add(user)
            
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def finalize_kyc(db: Session, user_id: int) -> User:
        """
        Check all documents. If Aadhaar and PAN (minimum) are verified, mark user as verified.
        """
        user = db.get(User, user_id)
        if not user:
            return None
            
        docs = db.exec(select(KYCDocument).where(KYCDocument.user_id == user_id, KYCDocument.status == "verified")).all()
        doc_types = {d.document_type for d in docs}
        
        # Business Rule: Need at least 'aadhaar' and 'pan' verified
        if "aadhaar" in doc_types and "pan" in doc_types:
            user.kyc_status = "verified"
            db.add(user)
            db.commit()
            db.refresh(user)
            
        return user
