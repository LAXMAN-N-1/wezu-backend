"""
QR Code Service
Generate and verify QR codes for battery verification
"""
import qrcode
import hashlib
import base64
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlmodel import Session, select
from app.core.config import settings
from app.models.battery import Battery
import logging

logger = logging.getLogger(__name__)

class QRCodeService:
    """QR code generation and verification service"""
    
    @staticmethod
    def generate_battery_qr(battery_id: int, session: Session) -> Optional[str]:
        """
        Generate QR code for battery
        
        Args:
            battery_id: Battery ID
            session: Database session
            
        Returns:
            Base64 encoded QR code image
        """
        try:
            battery = session.get(Battery, battery_id)
            if not battery:
                return None
            
            # Create QR data with timestamp and signature
            timestamp = int(datetime.utcnow().timestamp())
            data = f"{battery.serial_number}|{battery_id}|{timestamp}"
            
            # Generate signature
            signature = QRCodeService._generate_signature(data)
            qr_data = f"{data}|{signature}"
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return img_str
            
        except Exception as e:
            logger.error(f"QR code generation failed: {str(e)}")
            return None
    
    @staticmethod
    def verify_qr_code(qr_data: str, session: Session) -> Optional[Dict]:
        """
        Verify scanned QR code
        
        Args:
            qr_data: Scanned QR code data
            session: Database session
            
        Returns:
            Battery details if valid, None otherwise
        """
        try:
            # Parse QR data
            parts = qr_data.split('|')
            if len(parts) != 4:
                logger.error("Invalid QR code format")
                return None
            
            serial_number, battery_id, timestamp, signature = parts
            
            # Verify signature
            data = f"{serial_number}|{battery_id}|{timestamp}"
            expected_signature = QRCodeService._generate_signature(data)
            
            if signature != expected_signature:
                logger.error("Invalid QR code signature")
                return None
            
            # Check expiry (24 hours)
            qr_timestamp = datetime.fromtimestamp(int(timestamp))
            if datetime.utcnow() - qr_timestamp > timedelta(hours=24):
                logger.error("QR code expired")
                return None
            
            # Verify battery exists
            battery = session.get(Battery, int(battery_id))
            if not battery:
                logger.error("Battery not found")
                return None
            
            # Verify serial number matches
            if battery.serial_number != serial_number:
                logger.error("Serial number mismatch")
                return None
            
            return {
                "battery_id": battery.id,
                "serial_number": battery.serial_number,
                "model": battery.model,
                "capacity_mah": battery.capacity_mah,
                "health_percentage": battery.health_percentage,
                "status": battery.status,
                "verified_at": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"QR code verification failed: {str(e)}")
            return None
    
    @staticmethod
    def _generate_signature(data: str) -> str:
        """
        Generate HMAC signature for QR data
        
        Args:
            data: Data to sign
            
        Returns:
            Signature hash
        """
        secret = settings.QR_CODE_SECRET if hasattr(settings, 'QR_CODE_SECRET') else settings.SECRET_KEY
        signature = hashlib.sha256(f"{data}{secret}".encode()).hexdigest()
        return signature[:16]  # Use first 16 characters
