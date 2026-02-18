from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict
from datetime import datetime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.station import Station
    from app.models.commission import Commission # If it existed
    from app.models.staff import StaffProfile
# from pydantic import EmailStr
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

class DealerProfile(SQLModel, table=True):
    __tablename__ = "dealer_profiles"
    __table_args__ = {"schema": "dealers"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="core.users.id", unique=True)
    
    business_name: str
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    
    contact_person: str
    contact_email: str
    contact_phone: str
    
    address_line1: str
    city: str
    state: str
    pincode: str
    
    # Financial Details
    bank_details: Optional[Dict] = Field(default=None, sa_column=sa.Column(JSONB))
    
    is_active: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: "User" = Relationship(back_populates="dealer_profile")
    stations: List["Station"] = Relationship(back_populates="dealer")
    application: Optional["DealerApplication"] = Relationship(back_populates="dealer")
    # commissions: List["Commission"] = Relationship(back_populates="dealer")
    documents: List["DealerDocument"] = Relationship(back_populates="dealer")
    staff_members: List["StaffProfile"] = Relationship(back_populates="dealer")

class DealerDocument(SQLModel, table=True):
    __tablename__ = "dealer_documents"
    __table_args__ = {"schema": "dealers"}
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealers.dealer_profiles.id")
    document_type: str = Field(index=True) # gst, pan, registration, cancelled_cheque
    file_url: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    is_verified: bool = Field(default=False)
    
    dealer: DealerProfile = Relationship(back_populates="documents")

class DealerApplication(SQLModel, table=True):
    __tablename__ = "dealer_applications"
    __table_args__ = {"schema": "dealers"}
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealers.dealer_profiles.id", unique=True)
    
    # Stages: SUBMITTED, AUTO_VERIFIED, KYC_SUBMITTED, REVIEW_PENDING, 
    # FIELD_VISIT_SCHEDULED, FIELD_VISIT_COMPLETED, REJECTED, APPROVED
    current_stage: str = Field(default="SUBMITTED")
    
    risk_score: float = Field(default=0.0)
    
    # Using JSON for history log: [{"stage": "SUBMITTED", "timestamp": "...", "notes": ""}]
    status_history: List[Dict] = Field(default_factory=list, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    dealer: DealerProfile = Relationship(back_populates="application")
    field_visits: List["FieldVisit"] = Relationship(back_populates="application")

class FieldVisit(SQLModel, table=True):
    __tablename__ = "field_visits"
    __table_args__ = {"schema": "dealers"}
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="dealers.dealer_applications.id")
    officer_id: int = Field(foreign_key="core.users.id") # Field Officer
    
    scheduled_date: datetime
    completed_date: Optional[datetime] = None
    
    status: str = Field(default="SCHEDULED") # SCHEDULED, COMPLETED, CANCELLED
    
    report_data: Optional[Dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    images: Optional[List[str]] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    application: DealerApplication = Relationship(back_populates="field_visits")
