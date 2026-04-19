from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Optional

class VideoKYCCompleteRequest(BaseModel):
    verification_result: str # "approved", "rejected"
    recording_link: Optional[str] = None
    agent_notes: Optional[str] = None
