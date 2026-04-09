import hmac
import hashlib
import io
import base64
import qrcode
from typing import Optional, Dict, Any
from app.core.config import settings

class QRCodeService:
    @staticmethod
    def _generate_signature(data: str) -> str:
        """Create a signature for the QR data to prevent tampering"""
        return hmac.new(
            settings.SECRET_KEY.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()[:16]

    @staticmethod
    def generate_station_qr(station_id: int) -> str:
        """
        Generate a secure QR code for a station identification.
        """
        data = f"wezu://station/{station_id}"
        signature = QRCodeService._generate_signature(data)
        signed_data = f"{data}?sig={signature}"
        return QRCodeService._generate_base64_qr(signed_data)

    @staticmethod
    def generate_battery_qr(battery_id: int, session: Optional[Any] = None) -> str:
        """
        Generate a secure QR code for a battery identification.
        """
        data = f"wezu://battery/{battery_id}"
        signature = QRCodeService._generate_signature(data)
        signed_data = f"{data}?sig={signature}"
        return QRCodeService._generate_base64_qr(signed_data)

    @staticmethod
    def verify_qr_code(qr_data: str, session: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """
        Verify the signature of a scanned QR code.
        """
        if "?sig=" not in qr_data:
            return None
            
        base_data, signature = qr_data.split("?sig=")
        expected_signature = QRCodeService._generate_signature(base_data)
        
        if not hmac.compare_digest(signature, expected_signature):
            return None
            
        # Parse resource type and ID
        try:
            parts = base_data.replace("wezu://", "").split("/")
            return {
                "type": parts[0],
                "id": int(parts[1])
            }
        except Exception:
            return None

    @staticmethod
    def _generate_base64_qr(data: str) -> str:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    @staticmethod
    def generate_qr_code_bytes(data: str) -> io.BytesIO:
        """
        Generate a QR code and return it as a byte stream (PNG).
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

