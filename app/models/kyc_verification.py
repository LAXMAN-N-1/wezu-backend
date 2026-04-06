"""
Backward-compatibility alias for KYCVerification.
The unified codebase uses KYCRecord from app.models.kyc.
"""
from app.models.kyc import KYCRecord as KYCVerification

__all__ = ["KYCVerification"]
