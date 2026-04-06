from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
import os
import socket
import threading
from typing import Any, Callable

from sqlmodel import Session

from app.core.config import settings
from app.core.database import engine
from app.services.event_stream_service import EventStreamService, StreamMessage
from app.services.notification_outbox_service import NotificationOutboxService
from app.services.razorpay_webhook_service import RazorpayWebhookService
from app.services.redis_service import RedisService
from app.services.telematics_ingest_service import TelematicsIngestService

logger = logging.getLogger(__name__)


def _consumer_name(mode: str) -> str:
    base = (settings.EVENT_WORKER_CONSUMER_NAME or "worker").strip() or "worker"
    return f"{base}:{mode}:{socket.gethostname()}:{os.getpid()}"


def _dedupe_key(prefix: str, unique_key: str) -> str:
    digest = hashlib.sha256(unique_key.encode("utf-8")).hexdigest()
    return f"wezu:stream:dedupe:{prefix}:{digest}"


def _acquire_once(prefix: str, unique_key: str, ttl_seconds: int = 86400) -> bool:
    client = RedisService.get_client()
    if client is None:
        return True
    key = _dedupe_key(prefix, unique_key)
    try:
        return bool(client.set(key, "1", ex=max(60, ttl_seconds), nx=True))
    except Exception:
        return True


def _release_once(prefix: str, unique_key: str) -> None:
    client = RedisService.get_client()
    if client is None:
        return
    key = _dedupe_key(prefix, unique_key)
    try:
        client.delete(key)
    except Exception:
        return


def _process_telematics_event(event: dict[str, Any]) -> None:
    payload = event.get("payload") or {}
    data_in = TelematicsIngestService.ingest_payload_from_dict(payload)
    dedupe_id = event.get("idempotency_key") or f"{data_in.battery_id}:{data_in.timestamp.isoformat()}"
    if not _acquire_once("telematics", dedupe_id):
        logger.info("Skipping duplicate telematics event id=%s", event.get("event_id"))
        return

    try:
        with Session(engine) as session:
            TelematicsIngestService.persist_telemetry(session, data_in=data_in)
    except Exception:
        _release_once("telematics", dedupe_id)
        raise


def _process_webhook_event(event: dict[str, Any]) -> None:
    payload_wrapper = event.get("payload") or {}
    payload = payload_wrapper.get("payload") if isinstance(payload_wrapper, dict) else {}
    if not isinstance(payload, dict):
        raise ValueError("Invalid webhook payload envelope")

    event_id = str(event.get("event_id") or "").strip()
    if not event_id:
        event_id = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    if not RazorpayWebhookService.try_mark_event_processing(event_id):
        logger.info("Skipping duplicate webhook event_id=%s", event_id)
        return

    try:
        with Session(engine) as session:
            RazorpayWebhookService.process_event(session, payload)
    except Exception:
        RazorpayWebhookService.clear_processing_marker(event_id)
        raise


def _process_notification_event(event: dict[str, Any]) -> None:
    payload = event.get("payload") or {}
    notification_id = payload.get("notification_id") if isinstance(payload, dict) else None
    if not notification_id:
        raise ValueError("notification_id missing")
    notification_id = int(notification_id)
    dedupe_id = event.get("idempotency_key") or f"notification:{notification_id}"
    if not _acquire_once("notification", dedupe_id):
        logger.info("Skipping duplicate notification event id=%s", event.get("event_id"))
        return

    try:
        NotificationOutboxService.dispatch_for_notification(notification_id)
    except Exception:
        _release_once("notification", dedupe_id)
        raise


def _run_stream_worker(
    *,
    mode: str,
    stream_name: str,
    group_name: str,
    dlq_stream_name: str,
    batch_size: int,
    block_ms: int,
    max_retries: int,
    process_fn: Callable[[dict[str, Any]], None],
    stop_event: threading.Event,
) -> None:
    consumer = _consumer_name(mode)
    while not stop_event.is_set():
        if EventStreamService.ensure_group(stream_name, group_name):
            break
        logger.warning(
            "Unable to initialize stream worker mode=%s stream=%s; retrying in 5s",
            mode,
            stream_name,
        )
        stop_event.wait(timeout=5)
    if stop_event.is_set():
        return

    logger.info(
        "Started stream worker mode=%s stream=%s group=%s consumer=%s",
        mode,
        stream_name,
        group_name,
        consumer,
    )

    while not stop_event.is_set():
        messages = EventStreamService.read_group(
            stream=stream_name,
            group=group_name,
            consumer=consumer,
            count=max(1, batch_size),
            block_ms=max(200, block_ms),
        )
        if not messages:
            continue

        for message in messages:
            if stop_event.is_set():
                break
            event = EventStreamService.deserialize_event(message.fields)
            try:
                process_fn(event)
                EventStreamService.ack(stream_name, group_name, message.message_id)
            except Exception as exc:
                logger.exception(
                    "Stream worker mode=%s failed message_id=%s event_type=%s: %s",
                    mode,
                    message.message_id,
                    event.get("event_type"),
                    exc,
                )
                EventStreamService.move_to_retry_or_dlq(
                    source_stream=stream_name,
                    dlq_stream=dlq_stream_name,
                    group=group_name,
                    message=message,
                    max_retries=max_retries,
                    error_text=str(exc),
                )


def run_telematics_ingest_worker(stop_event: threading.Event) -> None:
    _run_stream_worker(
        mode="telematics",
        stream_name=settings.TELEMATICS_STREAM_NAME,
        group_name=settings.TELEMATICS_STREAM_GROUP,
        dlq_stream_name=settings.TELEMATICS_STREAM_DLQ_NAME,
        batch_size=int(settings.TELEMATICS_STREAM_CONSUMER_BATCH_SIZE),
        block_ms=int(settings.TELEMATICS_STREAM_BLOCK_MS),
        max_retries=int(settings.TELEMATICS_STREAM_MAX_RETRIES),
        process_fn=_process_telematics_event,
        stop_event=stop_event,
    )


def run_webhook_worker(stop_event: threading.Event) -> None:
    _run_stream_worker(
        mode="webhook",
        stream_name=settings.WEBHOOK_STREAM_NAME,
        group_name=settings.WEBHOOK_STREAM_GROUP,
        dlq_stream_name=settings.WEBHOOK_STREAM_DLQ_NAME,
        batch_size=int(settings.WEBHOOK_STREAM_CONSUMER_BATCH_SIZE),
        block_ms=int(settings.WEBHOOK_STREAM_BLOCK_MS),
        max_retries=int(settings.WEBHOOK_STREAM_MAX_RETRIES),
        process_fn=_process_webhook_event,
        stop_event=stop_event,
    )


def run_notification_worker(stop_event: threading.Event) -> None:
    _run_stream_worker(
        mode="notification",
        stream_name=settings.NOTIFICATION_STREAM_NAME,
        group_name=settings.NOTIFICATION_STREAM_GROUP,
        dlq_stream_name=settings.NOTIFICATION_STREAM_DLQ_NAME,
        batch_size=int(settings.NOTIFICATION_STREAM_CONSUMER_BATCH_SIZE),
        block_ms=int(settings.NOTIFICATION_STREAM_BLOCK_MS),
        max_retries=int(settings.NOTIFICATION_STREAM_MAX_RETRIES),
        process_fn=_process_notification_event,
        stop_event=stop_event,
    )


def get_stream_worker_state() -> dict[str, Any]:
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "enabled": bool(settings.ENABLE_EVENT_STREAMS),
        "telematics": {
            "stream": settings.TELEMATICS_STREAM_NAME,
            "group": settings.TELEMATICS_STREAM_GROUP,
            "dlq_stream": settings.TELEMATICS_STREAM_DLQ_NAME,
            "pending": EventStreamService.pending_count(settings.TELEMATICS_STREAM_NAME, settings.TELEMATICS_STREAM_GROUP),
        },
        "webhooks": {
            "stream": settings.WEBHOOK_STREAM_NAME,
            "group": settings.WEBHOOK_STREAM_GROUP,
            "dlq_stream": settings.WEBHOOK_STREAM_DLQ_NAME,
            "pending": EventStreamService.pending_count(settings.WEBHOOK_STREAM_NAME, settings.WEBHOOK_STREAM_GROUP),
        },
        "notifications": {
            "stream": settings.NOTIFICATION_STREAM_NAME,
            "group": settings.NOTIFICATION_STREAM_GROUP,
            "dlq_stream": settings.NOTIFICATION_STREAM_DLQ_NAME,
            "pending": EventStreamService.pending_count(settings.NOTIFICATION_STREAM_NAME, settings.NOTIFICATION_STREAM_GROUP),
        },
    }
