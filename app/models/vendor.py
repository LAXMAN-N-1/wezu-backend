from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.models.location import Zone

class Vendor(SQLModel, table=True):
    __tablename__ = "vendors"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Business Details
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    phone: str
    license_number: Optional[str] = None
    
    # Contract Details
    commission_rate: float = Field(default=15.0) # Percentage
    contract_start_date: Optional[datetime] = None
    contract_end_date: Optional[datetime] = None
    
    # Status
    status: str = Field(default="pending") # pending, active, suspended, rejected
    
    # Location Link (Primary Zone)
    zone_id: Optional[int] = Field(default=None, foreign_key="zones.id")
    address: Optional[str] = None
    gps_coordinates: Optional[str] = None # "lat,long"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    documents: List["VendorDocument"] = Relationship(back_populates="vendor")
    settlements: List["Settlement"] = Relationship(back_populates="vendor")
    # stations: List["Station"] = Relationship(back_populates="vendor") # To be linked in Station

class VendorDocument(SQLModel, table=True):
    __tablename__ = "vendor_documents"
    # __table_args__ = {"schema": "public"}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    vendor_id: int = Field(foreign_key="vendors.id")
    document_type: str = Field(index=True) # license, gst, agreement, other
    file_path: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    is_verified: bool = Field(default=False)
    
    vendor: Vendor = Relationship(back_populates="documents")
