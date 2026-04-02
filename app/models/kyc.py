from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Any, TYPE_CHECKING
from datetime import datetime, UTC
from enum import Enum
import uuid

if TYPE_CHECKING:
     from app.models.user import User

class KYCDocumentType(str, Enum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    DRIVING_LICENSE = "driving_license"
    PASSPORT = "passport"

class KYCDocumentStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class KYCRecord(SQLModel, table=True):
    __tablename__ = "kyc_records"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    # Encrypted identifiers
    aadhaar_number_enc: Optional[str] = None
    pan_number_enc: Optional[str] = None
    
    # Document URLs
    aadhaar_front_url: Optional[str] = None
    aadhaar_back_url: Optional[str] = None
    pan_card_url: Optional[str] = None
    video_kyc_url: Optional[str] = None
    utility_bill_url: Optional[str] = None
    
    # Verification details
    status: str = Field(default="pending", index=True) # pending, verified, rejected, partial
    liveness_score: Optional[float] = None
    verification_response: Optional[str] = None # JSON string
    rejection_reason: Optional[str] = None
    
    # Audit
    verified_by: Optional[int] = Field(default=None, foreign_key="users.id") # Admin User ID
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verified_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationship
    user: "User" = Relationship(back_populates="kyc_records", sa_relationship_kwargs={"foreign_keys": "[KYCRecord.user_id]"})

class KYCDocument(SQLModel, table=True):
    __tablename__ = "kyc_documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    document_type: KYCDocumentType
    document_number: Optional[str] = None # Encrypted
    
    file_url: str
    status: KYCDocumentStatus = Field(default=KYCDocumentStatus.PENDING)
    
    verification_response: Optional[str] = None # JSON string
    rejection_reason: Optional[str] = None
    
    verified_by: Optional[int] = Field(default=None, foreign_key="users.id")
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verified_at: Optional[datetime] = None
    
    # Relationships
    user: "User" = Relationship(
        back_populates="kyc_documents",
        sa_relationship_kwargs={"foreign_keys": "[KYCDocument.user_id]"}
    )

class KYCRequest(SQLModel, table=True):
    __tablename__ = "kyc_requests"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    status: str = Field(default="pending")
    request_data: Optional[str] = None # JSON string
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
