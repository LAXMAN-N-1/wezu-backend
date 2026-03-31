from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict
from datetime import datetime, UTC
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
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    
    business_name: str
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    
    # Extra Business Info
    year_established: Optional[str] = None
    website_url: Optional[str] = None
    business_description: Optional[str] = None
    
    contact_person: str
    contact_email: str
    contact_phone: str
    alternate_phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    
    address_line1: str
    city: str
    state: str
    pincode: str
    
    # Financial Details
    bank_details: Optional[Dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    # Global Settings Defaults
    global_station_defaults: Optional[Dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    global_inventory_rules: Optional[Dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    holiday_calendar: Optional[List[Dict]] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    is_active: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Relationships
    user: "User" = Relationship(
        back_populates="dealer_profile",
        sa_relationship_kwargs={"foreign_keys": "[DealerProfile.user_id]"}
    )
    stations: List["Station"] = Relationship(back_populates="dealer")
    application: Optional["DealerApplication"] = Relationship(back_populates="dealer")
    # commissions: List["Commission"] = Relationship(back_populates="dealer")
    documents: List["DealerDocument"] = Relationship(back_populates="dealer")
    staff_members: List["StaffProfile"] = Relationship(back_populates="dealer")
    settlements: List["Settlement"] = Relationship(back_populates="dealer")

class DealerDocument(SQLModel, table=True):
    __tablename__ = "dealer_documents"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealer_profiles.id")
    document_type: str = Field(index=True) # gst, pan, registration, cancelled_cheque
    category: Optional[str] = Field(default="verification") # verification, business, operational
    
    file_url: str
    version: int = Field(default=1)
    status: str = Field(default="PENDING") # PENDING, VERIFIED, REJECTED, EXPIRED, ARCHIVED
    
    valid_until: Optional[datetime] = None
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_verified: bool = Field(default=False)
    
    dealer: "DealerProfile" = Relationship(back_populates="documents")

class DealerApplication(SQLModel, table=True):
    __tablename__ = "dealer_applications"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    dealer_id: int = Field(foreign_key="dealer_profiles.id", unique=True)
    
    # Stages: SUBMITTED, AUTOMATED_CHECKS_PASSED, KYC_SUBMITTED, MANUAL_REVIEW_PASSED, 
    # FIELD_VISIT_SCHEDULED, FIELD_VISIT_COMPLETED, REJECTED, APPROVED, TRAINING_COMPLETED, ACTIVE
    current_stage: str = Field(default="SUBMITTED")
    
    risk_score: float = Field(default=0.0)
    
    # Using JSON for history log: [{"stage": "SUBMITTED", "timestamp": "...", "notes": ""}]
    status_history: List[Dict] = Field(default_factory=list, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    dealer: "DealerProfile" = Relationship(back_populates="application")
    field_visits: List["FieldVisit"] = Relationship(back_populates="application")
    
    def log_stage(self, new_stage: str, notes: str = ""):
        self.current_stage = new_stage
        self.updated_at = datetime.now(UTC)
        # Create a new list if it's None or empty, then append the new entry
        history = list(self.status_history) if self.status_history else []
        history.append({
            "stage": new_stage,
            "timestamp": self.updated_at.isoformat(),
            "notes": notes
        })
        self.status_history = history

class FieldVisit(SQLModel, table=True):
    __tablename__ = "field_visits"
    # __table_args__ = {"schema": "public"}
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="dealer_applications.id")
    officer_id: int = Field(foreign_key="users.id") # Field Officer
    
    scheduled_date: datetime
    completed_date: Optional[datetime] = None
    
    status: str = Field(default="SCHEDULED") # SCHEDULED, COMPLETED, CANCELLED
    
    report_data: Optional[Dict] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    images: Optional[List[str]] = Field(default=None, sa_column=sa.Column(JSON().with_variant(JSONB, "postgresql")))
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    application: DealerApplication = Relationship(back_populates="field_visits")
