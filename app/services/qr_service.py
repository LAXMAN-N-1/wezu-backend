from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.models.battery import Battery
from app.services.battery_consistency import normalize_battery_serial


@dataclass(frozen=True)
class ResolvedBatteryQR:
    battery: Battery
    source: str
    raw_value: str


class BatteryQRCodeService:
    """
    Production QR service for battery identity.

    Design goals:
    - App compatibility: can generate QR values that scan to raw serial numbers.
    - Integrity: can generate a signed token (HMAC) for tamper-evident scans.
    - Backward compatibility: resolves plain serials, deep links, and legacy stored qr_code_data.
    """

    TOKEN_PREFIX = "WZB1"
    TOKEN_VERSION = 1
    TOKEN_TYPE = "battery"
    IMAGE_CONTENT_TYPE = "image/png"

    @classmethod
    def build_app_scan_value(cls, serial_number: str) -> str:
        return normalize_battery_serial(serial_number, field_name="serial_number")

    @classmethod
    def build_signed_scan_value(cls, *, battery_id: int, serial_number: str) -> str:
        serial = normalize_battery_serial(serial_number, field_name="serial_number")
        payload = {
            "v": cls.TOKEN_VERSION,
            "t": cls.TOKEN_TYPE,
            "bid": int(battery_id),
            "sn": serial,
        }
        payload_bytes = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        payload_b64 = cls._b64url_encode(payload_bytes)
        signature = hmac.new(
            cls._qr_signing_key(),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature_b64 = cls._b64url_encode(signature)
        return f"{cls.TOKEN_PREFIX}.{payload_b64}.{signature_b64}"

    @classmethod
    def parse_signed_scan_value(cls, token: str) -> Optional[dict[str, Any]]:
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != cls.TOKEN_PREFIX:
            return None

        payload_b64 = parts[1]
        signature_b64 = parts[2]
        expected_signature = hmac.new(
            cls._qr_signing_key(),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature_b64, cls._b64url_encode(expected_signature)):
            return None

        payload_bytes = cls._b64url_decode(payload_b64)
        if payload_bytes is None:
            return None

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        try:
            if int(payload.get("v")) != cls.TOKEN_VERSION:
                return None
            if payload.get("t") != cls.TOKEN_TYPE:
                return None

            battery_id = int(payload.get("bid"))
            if battery_id <= 0:
                return None

            serial = normalize_battery_serial(payload.get("sn"), field_name="sn")
        except Exception:
            return None

        return {
            "battery_id": battery_id,
            "serial_number": serial,
        }

    @classmethod
    def ensure_battery_qr_identity(
        cls,
        battery: Battery,
        *,
        force: bool = False,
    ) -> str:
        if battery.id is None:
            raise ValueError("battery.id is required before generating QR identity")

        serial = normalize_battery_serial(battery.serial_number, field_name="serial_number")
        battery.serial_number = serial

        if battery.qr_code_data and not force:
            return battery.qr_code_data

        token = cls.build_signed_scan_value(
            battery_id=battery.id,
            serial_number=serial,
        )
        battery.qr_code_data = token
        return token

    @classmethod
    def generate_qr_base64(cls, data: str) -> str:
        try:
            import qrcode
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            raise RuntimeError(
                "qrcode package is required for QR image generation. Install dependencies from requirements.txt."
            ) from exc

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3,
        )
        qr.add_data(data)
        qr.make(fit=True)

        image = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    @classmethod
    def build_qr_bundle(
        cls,
        battery: Battery,
        *,
        mode: str = "app",
    ) -> dict[str, Any]:
        serial = normalize_battery_serial(battery.serial_number, field_name="serial_number")
        app_scan_value = cls.build_app_scan_value(serial)
        secure_scan_value = cls.ensure_battery_qr_identity(battery)

        selected_mode = mode.strip().lower()
        if selected_mode not in {"app", "secure"}:
            selected_mode = "app"

        selected_scan_value = app_scan_value if selected_mode == "app" else secure_scan_value
        qr_code_base64 = cls.generate_qr_base64(selected_scan_value)
        return {
            "battery_id": battery.id,
            "serial_number": serial,
            "mode": selected_mode,
            "scan_value": selected_scan_value,
            "app_scan_value": app_scan_value,
            "secure_scan_value": secure_scan_value,
            "qr_code_base64": qr_code_base64,
            "qr_code_data_uri": f"data:{cls.IMAGE_CONTENT_TYPE};base64,{qr_code_base64}",
            "content_type": cls.IMAGE_CONTENT_TYPE,
        }

    @classmethod
    def resolve_scanned_value(
        cls,
        session: Session,
        scanned_value: str,
    ) -> Optional[ResolvedBatteryQR]:
        raw_value = (scanned_value or "").strip()
        if not raw_value:
            return None

        signed_payload = cls.parse_signed_scan_value(raw_value)
        if signed_payload is not None:
            battery = session.get(Battery, signed_payload["battery_id"])
            if battery:
                battery_serial = normalize_battery_serial(
                    battery.serial_number,
                    field_name="serial_number",
                )
                if battery_serial == signed_payload["serial_number"]:
                    return ResolvedBatteryQR(
                        battery=battery,
                        source="signed_token",
                        raw_value=raw_value,
                    )

        deep_link_match = cls._parse_battery_deep_link(raw_value)
        if deep_link_match is not None:
            battery = cls._resolve_by_reference(session, deep_link_match)
            if battery:
                return ResolvedBatteryQR(
                    battery=battery,
                    source="deep_link",
                    raw_value=raw_value,
                )

        by_exact_qr = session.exec(
            select(Battery).where(Battery.qr_code_data == raw_value)
        ).first()
        if by_exact_qr is not None:
            return ResolvedBatteryQR(
                battery=by_exact_qr,
                source="stored_qr",
                raw_value=raw_value,
            )

        battery = cls._resolve_by_reference(session, raw_value)
        if battery is not None:
            return ResolvedBatteryQR(
                battery=battery,
                source="reference",
                raw_value=raw_value,
            )

        return None

    @classmethod
    def _resolve_by_reference(cls, session: Session, reference: str) -> Optional[Battery]:
        value = reference.strip()
        if not value:
            return None

        if value.isdigit():
            battery = session.get(Battery, int(value))
            if battery:
                return battery

        try:
            serial = normalize_battery_serial(value, field_name="reference")
        except Exception:
            return None

        rows = session.exec(
            select(Battery).where(func.upper(Battery.serial_number) == serial)
        ).all()
        if len(rows) > 1:
            # Explicitly fail closed on integrity violations.
            return None
        return rows[0] if rows else None

    @classmethod
    def _parse_battery_deep_link(cls, value: str) -> Optional[str]:
        parsed = urlparse(value)
        if parsed.scheme.lower() != "wezu":
            return None
        if parsed.netloc.lower() != "battery":
            return None

        path_value = parsed.path.strip("/")
        if not path_value:
            return None
        return path_value

    @classmethod
    def _qr_signing_key(cls) -> bytes:
        key = settings.QR_SIGNING_KEY or settings.SECRET_KEY
        return key.encode("utf-8")

    @staticmethod
    def _b64url_encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _b64url_decode(encoded: str) -> Optional[bytes]:
        padded = encoded + ("=" * ((4 - len(encoded) % 4) % 4))
        try:
            return base64.urlsafe_b64decode(padded.encode("ascii"))
        except Exception:
            return None


class QRService:
    """
    Backward-compatible wrapper retained for existing imports.
    """

    @staticmethod
    def generate_station_qr(station_id: int) -> str:
        return BatteryQRCodeService.generate_qr_base64(f"wezu://station/{station_id}")

    @staticmethod
    def generate_battery_qr(battery_id: str) -> str:
        return BatteryQRCodeService.generate_qr_base64(str(battery_id))


class QRCodeService:
    """
    Backward-compatible facade for legacy batteries_qr API module.
    """

    @staticmethod
    def generate_battery_qr(battery_id: int, session: Session) -> Optional[str]:
        battery = session.get(Battery, battery_id)
        if not battery:
            return None
        bundle = BatteryQRCodeService.build_qr_bundle(battery, mode="app")
        return bundle["qr_code_base64"]

    @staticmethod
    def verify_qr_code(qr_data: str, session: Session) -> Optional[dict[str, Any]]:
        resolved = BatteryQRCodeService.resolve_scanned_value(session, qr_data)
        if not resolved:
            return None
        battery = resolved.battery
        return {
            "battery_id": battery.id,
            "serial_number": battery.serial_number,
            "status": battery.status,
            "location_type": battery.location_type,
            "location_id": battery.location_id,
            "resolved_by": resolved.source,
        }
