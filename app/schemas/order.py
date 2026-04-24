from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.public_url import to_public_url


def _extract_status_candidate(raw_status: Any) -> Optional[Any]:
    if raw_status is None:
        return None
    if isinstance(raw_status, dict):
        for nested_key in ("value", "status", "name", "code", "id"):
            if raw_status.get(nested_key) is not None:
                return raw_status.get(nested_key)
        return None
    return raw_status


def _status_from_numeric_code(code_value: int) -> Optional[str]:
    code_map = {
        0: "pending",
        1: "assigned",
        2: "in_progress",
        3: "out_for_delivery",
        4: "completed",
        5: "canceled",
        6: "failed",
    }
    return code_map.get(code_value)


def _resolve_media_url(raw_url: Optional[str]) -> Optional[str]:
    if raw_url is None:
        return None

    value = str(raw_url).strip()
    if not value:
        return None

    return to_public_url(value)


class OrderCreate(BaseModel):
    units: int
    destination: str
    notes: Optional[str] = None
    customer_name: Optional[str] = "Walk-in Customer"
    customer_phone: Optional[str] = None
    priority: Optional[str] = "normal"
    total_value: Optional[Decimal] = Decimal("0.0")
    status: Optional[str] = "pending"

    order_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    estimated_delivery: Optional[datetime] = None
    dispatch_date: Optional[datetime] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    id: Optional[str] = None
    tracking_number: Optional[str] = None
    assigned_battery_ids: List[str]
    assigned_driver_id: Optional[int] = None

    type: Optional[str] = "delivery"
    original_order_id: Optional[str] = None
    refund_status: Optional[str] = "none"


class StatusUpdate(BaseModel):
    status: str
    failure_reason: Optional[str] = None
    dispatch_date: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_status_aliases(cls, value):
        if not isinstance(value, dict):
            return value

        status_candidate = None
        for status_key in ("status", "order_status", "current_status", "orderState", "state"):
            if status_key in value and value.get(status_key) is not None:
                status_candidate = _extract_status_candidate(value.get(status_key))
                if status_candidate is not None:
                    break

        if status_candidate is None:
            return value

        if isinstance(status_candidate, bool):
            raise ValueError("status must not be boolean")

        if isinstance(status_candidate, (int, float)):
            mapped_status = _status_from_numeric_code(int(status_candidate))
            value["status"] = mapped_status or str(int(status_candidate))
            return value

        status_text = str(status_candidate).strip()
        if not status_text:
            raise ValueError("status must not be empty")
        value["status"] = status_text
        return value


class ProofOfDeliveryCreate(BaseModel):
    image_url: str
    notes: Optional[str] = None
    signature_url: Optional[str] = None
    recipient_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_pod_aliases(cls, value):
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        nested_payload = payload.get("proof_of_delivery") or payload.get("proofOfDelivery")

        alias_map = {
            "image_url": "image_url",
            "imageUrl": "image_url",
            "proof_of_delivery_url": "image_url",
            "proofOfDeliveryUrl": "image_url",
            "signature_url": "signature_url",
            "signatureUrl": "signature_url",
            "proof_of_delivery_signature_url": "signature_url",
            "proofOfDeliverySignatureUrl": "signature_url",
            "recipient_name": "recipient_name",
            "recipientName": "recipient_name",
            "notes": "notes",
            "proof_of_delivery_notes": "notes",
            "proofOfDeliveryNotes": "notes",
        }

        for source_key, target_key in alias_map.items():
            source_value = payload.get(source_key)
            if source_value is not None and payload.get(target_key) is None:
                payload[target_key] = source_value

        if isinstance(nested_payload, dict):
            for source_key, target_key in alias_map.items():
                source_value = nested_payload.get(source_key)
                if source_value is not None and payload.get(target_key) is None:
                    payload[target_key] = source_value

        image_url = str(payload.get("image_url") or "").strip()
        if image_url:
            payload["image_url"] = image_url

        for optional_text_key in ("notes", "signature_url", "recipient_name"):
            if payload.get(optional_text_key) is None:
                continue
            cleaned = str(payload.get(optional_text_key)).strip()
            payload[optional_text_key] = cleaned or None

        return payload


class OrderSchedule(BaseModel):
    scheduled_slot_start: datetime
    scheduled_slot_end: datetime


class OrderRead(BaseModel):
    id: str
    status: str
    priority: str
    units: int
    destination: Optional[str] = None
    notes: Optional[str] = None
    customer_name: str
    customer_phone: Optional[str] = None
    total_value: Decimal = Decimal("0.0")
    tracking_number: Optional[str] = None
    assigned_battery_ids: Optional[str] = None
    assigned_driver_id: Optional[int] = None
    driver_id: Optional[int] = None
    assignedDriverId: Optional[int] = None
    is_driver_assigned: bool = False
    order_date: datetime
    estimated_delivery: Optional[datetime] = None
    dispatch_date: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    updated_at: datetime
    proof_of_delivery_url: Optional[str] = None
    proof_of_delivery_notes: Optional[str] = None
    proof_of_delivery_captured_at: Optional[datetime] = None
    proof_of_delivery_signature_url: Optional[str] = None
    recipient_name: Optional[str] = None
    proofOfDeliveryUrl: Optional[str] = None
    proofOfDeliveryNotes: Optional[str] = None
    proofOfDeliveryCapturedAt: Optional[datetime] = None
    proofOfDeliverySignatureUrl: Optional[str] = None
    recipientName: Optional[str] = None
    proof_of_delivery_public_url: Optional[str] = None
    proof_of_delivery_signature_public_url: Optional[str] = None
    proofOfDeliveryPublicUrl: Optional[str] = None
    proofOfDeliverySignaturePublicUrl: Optional[str] = None
    proof_of_delivery: Optional[dict[str, Any]] = None
    proofOfDelivery: Optional[dict[str, Any]] = None
    failure_reason: Optional[str] = None

    scheduled_slot_start: Optional[datetime] = None
    scheduled_slot_end: Optional[datetime] = None
    is_confirmed: bool = False
    confirmation_sent_at: Optional[datetime] = None

    type: str = "delivery"
    original_order_id: Optional[str] = None
    refund_status: str = "none"

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def set_driver_compat_fields(self):
        resolved_driver_id = (
            self.assigned_driver_id
            if self.assigned_driver_id is not None
            else self.driver_id
        )
        if resolved_driver_id is None:
            resolved_driver_id = self.assignedDriverId

        self.assigned_driver_id = resolved_driver_id
        self.driver_id = resolved_driver_id
        self.assignedDriverId = resolved_driver_id
        self.is_driver_assigned = resolved_driver_id is not None

        self.proofOfDeliveryUrl = self.proof_of_delivery_url
        self.proofOfDeliveryNotes = self.proof_of_delivery_notes
        self.proofOfDeliveryCapturedAt = self.proof_of_delivery_captured_at
        self.proofOfDeliverySignatureUrl = self.proof_of_delivery_signature_url
        self.recipientName = self.recipient_name
        self.proof_of_delivery_public_url = _resolve_media_url(self.proof_of_delivery_url)
        self.proof_of_delivery_signature_public_url = _resolve_media_url(self.proof_of_delivery_signature_url)
        self.proofOfDeliveryPublicUrl = self.proof_of_delivery_public_url
        self.proofOfDeliverySignaturePublicUrl = self.proof_of_delivery_signature_public_url

        pod_payload: Optional[dict[str, Any]] = None
        if any(
            field is not None
            for field in (
                self.proof_of_delivery_url,
                self.proof_of_delivery_notes,
                self.proof_of_delivery_captured_at,
                self.proof_of_delivery_signature_url,
                self.recipient_name,
            )
        ):
            pod_payload = {
                "image_url": self.proof_of_delivery_url,
                "image_public_url": self.proof_of_delivery_public_url,
                "notes": self.proof_of_delivery_notes,
                "captured_at": self.proof_of_delivery_captured_at,
                "signature_url": self.proof_of_delivery_signature_url,
                "signature_public_url": self.proof_of_delivery_signature_public_url,
                "recipient_name": self.recipient_name,
                "imageUrl": self.proof_of_delivery_url,
                "imagePublicUrl": self.proof_of_delivery_public_url,
                "capturedAt": self.proof_of_delivery_captured_at,
                "signatureUrl": self.proof_of_delivery_signature_url,
                "signaturePublicUrl": self.proof_of_delivery_signature_public_url,
                "recipientName": self.recipient_name,
            }

        self.proof_of_delivery = pod_payload
        self.proofOfDelivery = pod_payload
        return self
