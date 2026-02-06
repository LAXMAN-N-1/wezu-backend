from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class KYCDocumentBase(BaseModel):
    document_type: str
    document_number: Optional[str] = None

class KYCDocumentUpload(KYCDocumentBase):
    pass # File upload handled separately

class KYCDocumentResponse(KYCDocumentBase):
    id: int
    user_id: int
    file_url: str
    status: str
    uploaded_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class KYCStatusResponse(BaseModel):
    kyc_status: str
    documents: List[KYCDocumentResponse]
    rejection_reason: Optional[str] = None

class KYCSubmitRequest(BaseModel):
    aadhaar_number: Optional[str] = None
    pan_number: Optional[str] = None
