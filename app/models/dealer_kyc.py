from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict
from datetime import datetime
import enum
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

class KYCStateConfig(str, enum.Enum):
    REGISTRATION = "REGISTRATION"
    DOC_SUBMITTED = "DOC_SUBMITTED"
    AUTO_CHECKS = "AUTO_CHECKS"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"

class DealerKYCApplication(SQLModel, table=True):
    __tablename__ = "dealer_kyc_applications"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    
    company_name: str
    pan_number: str
    gst_number: str
    bank_details_json: str
    
    pan_doc_url: Optional[str] = None
    gst_doc_url: Optional[str] = None
    reg_cert_url: Optional[str] = None
    
    application_state: KYCStateConfig = Field(default=KYCStateConfig.REGISTRATION)
    
    admin_comments: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    transitions: List["KYCStateTransition"] = Relationship(back_populates="application")

class KYCStateTransition(SQLModel, table=True):
    __tablename__ = "kyc_state_transitions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="dealer_kyc_applications.id")
    
    from_state: str
    to_state: str
    reason: Optional[str] = None
    changed_by_user_id: Optional[int] = Field(foreign_key="users.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    application: DealerKYCApplication = Relationship(back_populates="transitions")
