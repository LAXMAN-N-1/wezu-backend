import qrcode
import io
import base64
from typing import Optional

class QRService:
    @staticmethod
    def generate_station_qr(station_id: int) -> str:
        """
        Generate a QR code for a station identification.
        Encodes a JSON or URL that the mobile app can parse.
        Returns a base64 encoded string of the QR image.
        """
        data = f"wezu://station/{station_id}"
        return QRService._generate_base64_qr(data)

    @staticmethod
    def generate_battery_qr(battery_id: str) -> str:
        """
        Generate a QR code for a battery identification.
        Returns a base64 encoded string of the QR image.
        """
        data = f"wezu://battery/{battery_id}"
        return QRService._generate_base64_qr(data)

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
