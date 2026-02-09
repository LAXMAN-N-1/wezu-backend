from pydantic import BaseModel
from typing import Optional, Dict

class KYCRejectRequest(BaseModel):
    reason: str
    rejection_reasons: Optional[Dict[int, str]] = None # map of doc_id -> reason
