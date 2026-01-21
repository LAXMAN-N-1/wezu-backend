"""
QR Code and Battery Verification API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from pydantic import BaseModel
from typing import Optional

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.battery import Battery
from app.services.qr_service import QRCodeService
from app.schemas.common import DataResponse

router = APIRouter()

# Schemas
class QRGenerateRequest(BaseModel):
    battery_id: int

class QRVerifyRequest(BaseModel):
    qr_data: str

# QR Code Endpoints
@router.post("/qr/generate", response_model=DataResponse[dict])
def generate_qr_code(
    request: QRGenerateRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Generate QR code for battery verification
    Admin or station staff only
    """
    # Verify battery exists
    battery = session.get(Battery, request.battery_id)
    if not battery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Battery not found"
        )
    
    # Generate QR code
    qr_image = QRCodeService.generate_battery_qr(request.battery_id, session)
    if not qr_image:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate QR code"
        )
    
    return DataResponse(
        success=True,
        data={
            "battery_id": battery.id,
            "serial_number": battery.serial_number,
            "qr_code": qr_image,  # Base64 encoded image
            "expires_in_hours": 24
        }
    )

@router.post("/qr/verify", response_model=DataResponse[dict])
def verify_qr_code(
    request: QRVerifyRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Verify scanned QR code and get battery details
    Customer endpoint for rental verification
    """
    # Verify QR code
    battery_data = QRCodeService.verify_qr_code(request.qr_data, session)
    if not battery_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired QR code"
        )
    
    return DataResponse(
        success=True,
        data=battery_data
    )

@router.get("/{battery_id}/qr", response_model=DataResponse[dict])
def get_battery_qr(
    battery_id: int,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get QR code for specific battery"""
    qr_image = QRCodeService.generate_battery_qr(battery_id, session)
    if not qr_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Battery not found or QR generation failed"
        )
    
    return DataResponse(
        success=True,
        data={
            "battery_id": battery_id,
            "qr_code": qr_image
        }
    )
