from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime

class KYCDocument(SQLModel, table=True):
    __tablename__ = "kyc_documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    document_type: str # aadhaar, pan, utility_bill, photo, video
    document_number: Optional[str] = None
    file_url: str
    status: str = "pending" # pending, verified, rejected
    verification_response: Optional[str] = None # JSON string or similar
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationship
    user: "User" = Relationship(back_populates="kyc_documents")

class KYCRequest(SQLModel):
    # This might not be a table if we just track status on user, but good for history
    pass
