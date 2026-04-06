from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.core.config import settings
from app.models.financial import Transaction
from app.models.refund import Refund
from app.services.event_stream_service import EventStreamService
from app.services.redis_service import RedisService
from app.services.wallet_service import WalletService

logger = logging.getLogger(__name__)


class RazorpayWebhookService:
    """Canonical Razorpay webhook ingestion and business handling."""

    @staticmethod
    def verify_signature(body: bytes, signature: str | None) -> bool:
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            return False
        if not signature:
            return False
        generated_signature = hmac.new(
            key=bytes(settings.RAZORPAY_WEBHOOK_SECRET, "utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(generated_signature, signature)

    @staticmethod
    def parse_payload(body: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Webhook payload must be a JSON object")
            return payload
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body") from exc

    @staticmethod
    def compute_event_id(body: bytes, explicit_event_id: str | None = None) -> str:
        if explicit_event_id:
            return explicit_event_id.strip()
        return hashlib.sha256(body).hexdigest()

    @staticmethod
    def enqueue_event(
        *,
        body: bytes,
        signature: str | None,
        payload: dict[str, Any],
        source: str,
        event_id: str | None = None,
    ) -> str | None:
        stream_event = EventStreamService.build_event(
            event_type="webhook.razorpay.v1",
            source=source,
            event_id=RazorpayWebhookService.compute_event_id(body, explicit_event_id=event_id),
            idempotency_key=RazorpayWebhookService.compute_event_id(body, explicit_event_id=event_id),
            payload={
                "payload": payload,
                "signature": signature,
            },
        )
        return EventStreamService.publish(settings.WEBHOOK_STREAM_NAME, stream_event)

    @staticmethod
    def _processed_key(event_id: str) -> str:
        return f"wezu:webhook:processed:{event_id}"

    @staticmethod
    def try_mark_event_processing(event_id: str, ttl_seconds: int = 86400) -> bool:
        client = RedisService.get_client()
        if client is None:
            return True
        try:
            return bool(client.set(RazorpayWebhookService._processed_key(event_id), "1", nx=True, ex=ttl_seconds))
        except Exception:
            return True

    @staticmethod
    def clear_processing_marker(event_id: str) -> None:
        client = RedisService.get_client()
        if client is None:
            return
        try:
            client.delete(RazorpayWebhookService._processed_key(event_id))
        except Exception:
            return

    @staticmethod
    def _handle_payment_captured(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
        payment_entity = payload.get("payment", {}).get("entity", {})
        payment_id = payment_entity.get("id")
        order_id = payment_entity.get("order_id")
        amount_paise = payment_entity.get("amount", 0)
        notes_user_id = payment_entity.get("notes", {}).get("user_id")

        if not payment_id or not order_id:
            logger.warning("Ignored payment.captured webhook due to missing payment_id/order_id")
            return {"status": "ignored", "reason": "missing payment_id/order_id"}

        try:
            amount = (Decimal(str(amount_paise)) / Decimal("100")).quantize(Decimal("0.01"))
        except Exception:
            return {"status": "ignored", "reason": "invalid amount"}
        if amount <= 0:
            return {"status": "ignored", "reason": "non_positive amount"}

        noted_user_id = None
        if notes_user_id is not None:
            try:
                noted_user_id = int(notes_user_id)
            except (TypeError, ValueError):
                logger.warning("Invalid notes.user_id in payment.captured for order=%s", order_id)

        try:
            WalletService.apply_recharge_capture(
                db,
                order_id=order_id,
                payment_id=payment_id,
                amount=amount,
                noted_user_id=noted_user_id,
            )
        except HTTPException as exc:
            logger.warning(
                "Ignored payment.captured for order=%s payment=%s: %s",
                order_id,
                payment_id,
                exc.detail,
            )
            return {"status": "ignored", "reason": str(exc.detail)}

        return {"status": "ok", "order_id": order_id, "payment_id": payment_id}

    @staticmethod
    def _handle_payment_failed(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
        payment_entity = payload.get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id")

        if not order_id:
            return {"status": "ignored", "reason": "missing order_id"}

        WalletService.mark_recharge_intent_failed(db, order_id=order_id, payment_id=payment_id)
        return {"status": "ok", "order_id": order_id, "payment_id": payment_id}

    @staticmethod
    def _resolve_refund(db: Session, gateway_refund_id: str | None, payment_id: str | None) -> Refund | None:
        refund = None
        if gateway_refund_id:
            refund = db.exec(select(Refund).where(Refund.gateway_refund_id == gateway_refund_id)).first()
        if refund is None and payment_id:
            txn = db.exec(select(Transaction).where(Transaction.razorpay_payment_id == payment_id)).first()
            if txn:
                refund = db.exec(
                    select(Refund)
                    .where(Refund.transaction_id == txn.id)
                    .order_by(Refund.created_at.desc())
                ).first()
        return refund

    @staticmethod
    def _handle_refund_event(db: Session, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        refund_entity = payload.get("refund", {}).get("entity", {})
        gateway_refund_id = refund_entity.get("id")
        payment_id = refund_entity.get("payment_id")

        refund = RazorpayWebhookService._resolve_refund(db, gateway_refund_id, payment_id)
        if not refund:
            return {"status": "ignored", "reason": "refund record not found"}

        if gateway_refund_id:
            refund.gateway_refund_id = gateway_refund_id

        if event_type == "refund.processed":
            refund.status = "processed"
            refund.processed_at = datetime.utcnow()
        elif event_type == "refund.failed":
            refund.status = "failed"
        else:
            refund.status = "pending"

        db.add(refund)
        db.commit()
        return {
            "status": "ok",
            "gateway_refund_id": gateway_refund_id,
            "refund_status": refund.status,
        }

    @staticmethod
    def process_event(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
        event_type = str(payload.get("event") or "").strip().lower()
        event_payload = payload.get("payload", {})
        if not event_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing event type")

        if event_type == "payment.captured":
            result = RazorpayWebhookService._handle_payment_captured(db, event_payload)
        elif event_type == "payment.failed":
            result = RazorpayWebhookService._handle_payment_failed(db, event_payload)
        elif event_type in {"refund.created", "refund.processed", "refund.failed"}:
            result = RazorpayWebhookService._handle_refund_event(db, event_type, event_payload)
        else:
            result = {"status": "ignored", "reason": f"unsupported_event:{event_type}"}

        return {
            "status": result.get("status", "ok"),
            "event": event_type,
            "result": result,
        }
