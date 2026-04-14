from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.payment_method import PaymentMethod


class PaymentMethodService:
    _ALLOWED_TYPES = {"card", "upi", "wallet", "netbanking"}
    _METHOD_CATALOG = (
        {
            "id": "UPI",
            "type": "upi",
            "name": "UPI",
            "description": "Google Pay, PhonePe, Paytm, etc.",
            "icon": "upi",
            "enabled": True,
        },
        {
            "id": "CARD",
            "type": "card",
            "name": "Credit/Debit Card",
            "description": "Visa, Mastercard, RuPay",
            "icon": "card",
            "enabled": True,
        },
        {
            "id": "WALLET",
            "type": "wallet",
            "name": "Digital Wallet",
            "description": "Paytm, Amazon Pay, etc.",
            "icon": "wallet",
            "enabled": True,
        },
        {
            "id": "NETBANKING",
            "type": "netbanking",
            "name": "Net Banking",
            "description": "All major banks",
            "icon": "bank",
            "enabled": True,
        },
    )

    @staticmethod
    def _normalize_method_type(raw: str | None) -> str:
        method_type = (raw or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "net_banking": "netbanking",
            "netbank": "netbanking",
        }
        method_type = aliases.get(method_type, method_type)
        if method_type not in PaymentMethodService._ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported payment method type '{raw}'. Allowed: {sorted(PaymentMethodService._ALLOWED_TYPES)}",
            )
        return method_type

    @staticmethod
    def _normalize_provider(raw: str | None) -> str:
        provider = (raw or "razorpay").strip().lower()
        if not provider:
            provider = "razorpay"
        return provider

    @staticmethod
    def _normalize_provider_token(raw: str | None) -> str:
        token = (raw or "").strip()
        if not token:
            raise HTTPException(status_code=400, detail="provider_token is required")
        if len(token) > 255:
            raise HTTPException(status_code=400, detail="provider_token is too long")
        return token

    @staticmethod
    def _extract_last4(details: dict[str, Any], provider_token: str) -> str | None:
        last4 = str(details.get("last4", "")).strip()
        if last4 and len(last4) <= 4:
            return last4
        digits = "".join(ch for ch in provider_token if ch.isdigit())
        return digits[-4:] if len(digits) >= 4 else None

    @staticmethod
    def _serialize(method: PaymentMethod) -> dict[str, Any]:
        metadata = method.metadata_json or {}
        expiry = metadata.get("expiry")
        if not expiry and metadata.get("exp_month") and metadata.get("exp_year"):
            expiry = f"{metadata['exp_month']}/{metadata['exp_year']}"

        return {
            "id": str(method.id),
            "type": method.method_type,
            "provider": method.provider,
            "is_default": method.is_default,
            "last4": method.last4,
            "brand": method.brand,
            "expiry": expiry,
            "created_at": method.created_at.isoformat() if method.created_at else None,
        }

    @staticmethod
    def list_active_methods(db: Session, user_id: int) -> list[PaymentMethod]:
        return db.exec(
            select(PaymentMethod)
            .where(PaymentMethod.user_id == user_id)
            .where(PaymentMethod.status == "active")
            .order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc())
        ).all()

    @staticmethod
    def list_serialized_methods(db: Session, user_id: int) -> list[dict[str, Any]]:
        return [PaymentMethodService._serialize(method) for method in PaymentMethodService.list_active_methods(db, user_id)]

    @staticmethod
    def available_method_catalog() -> list[dict[str, Any]]:
        return [dict(item) for item in PaymentMethodService._METHOD_CATALOG]

    @staticmethod
    def add_method(
        db: Session,
        *,
        user_id: int,
        method_type: str,
        provider_token: str,
        provider: str = "razorpay",
        is_default: bool = False,
        details: dict[str, Any] | None = None,
    ) -> tuple[PaymentMethod, bool]:
        normalized_type = PaymentMethodService._normalize_method_type(method_type)
        normalized_provider = PaymentMethodService._normalize_provider(provider)
        normalized_token = PaymentMethodService._normalize_provider_token(provider_token)
        if details is None:
            metadata = {}
        elif isinstance(details, dict):
            metadata = details
        else:
            raise HTTPException(status_code=400, detail="details must be an object")

        existing = db.exec(
            select(PaymentMethod)
            .where(PaymentMethod.user_id == user_id)
            .where(PaymentMethod.provider == normalized_provider)
            .where(PaymentMethod.provider_token == normalized_token)
            .where(PaymentMethod.status == "active")
        ).first()
        if existing:
            if is_default and not existing.is_default:
                PaymentMethodService.set_default(db, user_id=user_id, method_id=existing.id)
                db.refresh(existing)
            return existing, False

        active_methods = PaymentMethodService.list_active_methods(db, user_id)
        should_be_default = bool(is_default) or len(active_methods) == 0

        now = datetime.utcnow()
        if should_be_default:
            for method in active_methods:
                method.is_default = False
                method.updated_at = now
                db.add(method)

        created = PaymentMethod(
            user_id=user_id,
            provider=normalized_provider,
            method_type=normalized_type,
            provider_token=normalized_token,
            last4=PaymentMethodService._extract_last4(metadata, normalized_token),
            brand=str(metadata.get("brand", "")).strip() or None,
            metadata_json=metadata,
            is_default=should_be_default,
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(created)
        db.commit()
        db.refresh(created)
        return created, True

    @staticmethod
    def delete_method(db: Session, *, user_id: int, method_id: int) -> None:
        method = db.exec(
            select(PaymentMethod)
            .where(PaymentMethod.id == method_id)
            .where(PaymentMethod.user_id == user_id)
            .where(PaymentMethod.status == "active")
        ).first()
        if not method:
            raise HTTPException(status_code=404, detail="Payment method not found")

        was_default = bool(method.is_default)
        method.status = "deleted"
        method.is_default = False
        method.updated_at = datetime.utcnow()
        db.add(method)

        if was_default:
            replacement = db.exec(
                select(PaymentMethod)
                .where(PaymentMethod.user_id == user_id)
                .where(PaymentMethod.status == "active")
                .where(PaymentMethod.id != method_id)
                .order_by(PaymentMethod.created_at.desc())
            ).first()
            if replacement:
                replacement.is_default = True
                replacement.updated_at = datetime.utcnow()
                db.add(replacement)

        db.commit()

    @staticmethod
    def set_default(db: Session, *, user_id: int, method_id: int) -> PaymentMethod:
        selected = db.exec(
            select(PaymentMethod)
            .where(PaymentMethod.id == method_id)
            .where(PaymentMethod.user_id == user_id)
            .where(PaymentMethod.status == "active")
        ).first()
        if not selected:
            raise HTTPException(status_code=404, detail="Payment method not found")

        now = datetime.utcnow()
        active_methods = PaymentMethodService.list_active_methods(db, user_id)
        for method in active_methods:
            method.is_default = method.id == selected.id
            method.updated_at = now
            db.add(method)

        db.commit()
        db.refresh(selected)
        return selected

    @staticmethod
    def serialize(method: PaymentMethod) -> dict[str, Any]:
        return PaymentMethodService._serialize(method)
