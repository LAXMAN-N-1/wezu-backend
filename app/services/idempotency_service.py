from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Optional

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.idempotency import IdempotencyKey

MAX_IDEMPOTENCY_KEY_LENGTH = 128


def normalize_idempotency_key(raw_key: Optional[str]) -> Optional[str]:
    if raw_key is None:
        return None

    key = raw_key.strip()
    if not key:
        return None

    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Idempotency-Key too long (max {MAX_IDEMPOTENCY_KEY_LENGTH} chars)",
        )

    return key


def _fingerprint_payload(payload: Any) -> str:
    encoded = jsonable_encoder(payload)
    canonical = json.dumps(encoded, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_request_fingerprint(payload: Any) -> str:
    return _fingerprint_payload(payload)


def get_idempotent_replay(
    session: Session,
    *,
    user_id: int,
    idempotency_key: Optional[str],
    request_method: str,
    request_path: str,
    request_fingerprint: str,
) -> Optional[dict]:
    if not idempotency_key:
        return None

    record = session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.idempotency_key == idempotency_key,
            IdempotencyKey.request_method == request_method,
            IdempotencyKey.request_path == request_path,
        )
    ).first()
    if not record:
        return None

    if record.expires_at <= datetime.utcnow():
        session.delete(record)
        session.commit()
        return None

    if record.request_fingerprint != request_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key reuse with different request payload is not allowed",
        )

    try:
        return json.loads(record.response_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Stored idempotent response is corrupted") from exc


def record_idempotent_response(
    session: Session,
    *,
    user_id: int,
    idempotency_key: Optional[str],
    request_method: str,
    request_path: str,
    request_fingerprint: str,
    response_status_code: int,
    response_payload: Any,
) -> None:
    if not idempotency_key:
        return

    existing = session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.idempotency_key == idempotency_key,
            IdempotencyKey.request_method == request_method,
            IdempotencyKey.request_path == request_path,
        )
    ).first()
    if existing:
        if existing.request_fingerprint != request_fingerprint:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key reuse with different request payload is not allowed",
            )
        return

    encoded_payload = jsonable_encoder(response_payload)
    record = IdempotencyKey(
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_fingerprint=request_fingerprint,
        response_status_code=response_status_code,
        response_payload=json.dumps(encoded_payload, sort_keys=True, separators=(",", ":")),
    )

    savepoint = session.begin_nested()
    try:
        session.add(record)
        session.flush()
        savepoint.commit()
        return
    except IntegrityError:
        savepoint.rollback()

    # Another in-flight request inserted this key first. Re-read and validate.
    concurrent_record = session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.idempotency_key == idempotency_key,
            IdempotencyKey.request_method == request_method,
            IdempotencyKey.request_path == request_path,
        )
    ).first()
    if not concurrent_record:
        raise HTTPException(
            status_code=500,
            detail="Unable to record idempotent response due to concurrent conflict",
        )

    if concurrent_record.request_fingerprint != request_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key reuse with different request payload is not allowed",
        )
