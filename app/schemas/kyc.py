from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict
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

class KYCQueueItem(BaseModel):
    user_id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    user_type: Optional[str] = "customer" # Derived from role
    submitted_at: Optional[datetime] = None
    documents: List[KYCDocumentResponse]
    
    model_config = ConfigDict(from_attributes=True)

class KYCQueueResponse(BaseModel):
    items: List[KYCQueueItem]
    total: int
    page: int
    size: int

class KYCVerifyRequest(BaseModel):
    decision: str # "approved", "rejected"
    notes: Optional[str] = None
    rejection_reasons: Optional[Dict[int, str]] = None # map of doc_id -> reason

class RejectionReasonResponse(BaseModel):
    code: str
    description: str

class KYCDashboardResponse(BaseModel):
    total_pending: int
    total_approved_today: int
    total_rejected_today: int
    submission_trend: Dict[str, int] # date -> count

class UtilityBillVerifyRequest(BaseModel):
    bill_type: str # electricity, water, postpaid_mobile
    provider_name: str

