from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import socket
from typing import Any
from uuid import uuid4

from redis import ResponseError

from app.core.config import settings
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamMessage:
    stream: str
    message_id: str
    fields: dict[str, str]


class EventStreamService:
    """Redis Streams helper for ingestion/webhook/workflow event processing."""

    @staticmethod
    def _client():
        return RedisService.get_client()

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _json_loads(raw: str | None) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            logger.warning("event_stream.json_decode_failed", exc_info=True)
            return None

    @staticmethod
    def build_event(
        *,
        event_type: str,
        payload: dict[str, Any],
        source: str,
        schema_version: str = "v1",
        event_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": schema_version,
            "event_type": event_type,
            "event_id": event_id or str(uuid4()),
            "idempotency_key": idempotency_key or "",
            "source": source,
            "occurred_at": datetime.utcnow().isoformat(),
            "producer_host": socket.gethostname(),
            "payload": payload,
            "metadata": metadata or {},
            "attempt": 0,
        }

    @staticmethod
    def serialize_event(event: dict[str, Any]) -> dict[str, str]:
        return {
            "schema_version": str(event.get("schema_version", "v1")),
            "event_type": str(event.get("event_type", "")),
            "event_id": str(event.get("event_id", "")),
            "idempotency_key": str(event.get("idempotency_key") or ""),
            "source": str(event.get("source", "")),
            "occurred_at": str(event.get("occurred_at", "")),
            "producer_host": str(event.get("producer_host", "")),
            "payload": EventStreamService._json_dumps(event.get("payload", {})),
            "metadata": EventStreamService._json_dumps(event.get("metadata", {})),
            "attempt": str(int(event.get("attempt", 0))),
        }

    @staticmethod
    def deserialize_event(fields: dict[str, str]) -> dict[str, Any]:
        return {
            "schema_version": fields.get("schema_version", "v1"),
            "event_type": fields.get("event_type"),
            "event_id": fields.get("event_id"),
            "idempotency_key": fields.get("idempotency_key") or None,
            "source": fields.get("source"),
            "occurred_at": fields.get("occurred_at"),
            "producer_host": fields.get("producer_host"),
            "payload": EventStreamService._json_loads(fields.get("payload")) or {},
            "metadata": EventStreamService._json_loads(fields.get("metadata")) or {},
            "attempt": int(fields.get("attempt") or 0),
        }

    @staticmethod
    def publish(stream: str, event: dict[str, Any], *, maxlen: int | None = None) -> str | None:
        if not settings.ENABLE_EVENT_STREAMS:
            return None
        client = EventStreamService._client()
        if client is None:
            return None
        max_stream_len = maxlen or max(1000, int(getattr(settings, "REDIS_STREAM_MAXLEN", 10000)))
        fields = EventStreamService.serialize_event(event)
        try:
            return client.xadd(stream, fields, maxlen=max_stream_len, approximate=True)
        except Exception as exc:
            logger.warning("Failed to publish stream event stream=%s type=%s error=%s", stream, fields.get("event_type"), exc)
            return None

    @staticmethod
    def ensure_group(stream: str, group: str) -> bool:
        client = EventStreamService._client()
        if client is None:
            return False
        try:
            client.xgroup_create(name=stream, groupname=group, id="$", mkstream=True)
            return True
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                return True
            logger.warning("Failed to ensure stream group stream=%s group=%s: %s", stream, group, exc)
            return False
        except Exception as exc:
            logger.warning("Failed to ensure stream group stream=%s group=%s: %s", stream, group, exc)
            return False

    @staticmethod
    def read_group(
        *,
        stream: str,
        group: str,
        consumer: str,
        count: int,
        block_ms: int,
    ) -> list[StreamMessage]:
        client = EventStreamService._client()
        if client is None:
            return []
        try:
            raw = client.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=max(1, count),
                block=max(100, block_ms),
            )
        except Exception as exc:
            logger.warning("Failed to read stream group stream=%s group=%s: %s", stream, group, exc)
            import time
            time.sleep(1)
            return []

        messages: list[StreamMessage] = []
        for stream_name, entries in raw or []:
            for message_id, fields in entries:
                mapped = {str(k): str(v) for k, v in (fields or {}).items()}
                messages.append(StreamMessage(stream=stream_name, message_id=message_id, fields=mapped))
        return messages

    @staticmethod
    def ack(stream: str, group: str, message_id: str) -> None:
        client = EventStreamService._client()
        if client is None:
            return
        try:
            client.xack(stream, group, message_id)
        except Exception:
            logger.warning("event_stream.ack_failed stream=%s msg=%s", stream, message_id, exc_info=True)
            return

    @staticmethod
    def move_to_retry_or_dlq(
        *,
        source_stream: str,
        dlq_stream: str,
        group: str,
        message: StreamMessage,
        max_retries: int,
        error_text: str,
    ) -> None:
        event = EventStreamService.deserialize_event(message.fields)
        current_attempt = int(event.get("attempt") or 0)
        next_attempt = current_attempt + 1
        event["attempt"] = next_attempt
        event["metadata"] = {
            **(event.get("metadata") or {}),
            "last_error": error_text[:500],
            "last_failure_at": datetime.utcnow().isoformat(),
            "last_failure_stream": source_stream,
        }

        target_stream = source_stream if next_attempt <= max_retries else dlq_stream
        published_id = EventStreamService.publish(target_stream, event)
        if published_id is None:
            logger.warning(
                "Unable to move failed message to retry/dlq; leaving pending stream=%s message_id=%s",
                source_stream,
                message.message_id,
            )
            return
        EventStreamService.ack(source_stream, group, message.message_id)

    @staticmethod
    def pending_count(stream: str, group: str) -> int | None:
        client = EventStreamService._client()
        if client is None:
            return None
        try:
            pending = client.xpending(stream, group)
            if isinstance(pending, dict):
                return int(pending.get("pending", 0))
            if isinstance(pending, (list, tuple)) and pending:
                return int(pending[0])
            return 0
        except Exception:
            logger.warning("event_stream.pending_count_failed stream=%s group=%s", stream, group, exc_info=True)
            return None
