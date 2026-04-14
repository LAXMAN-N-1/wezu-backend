from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
from typing import Any
import uuid

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.models.order_realtime_outbox import OrderRealtimeOutbox
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)

ORDER_UPDATES_CHANNEL = "wezu:orders:updates"
PENDING_STATUSES = {"pending", "failed"}
ORDER_DISPATCH_LOCK_KEY = "wezu:orders:outbox:dispatch_lock"


class OrderRealtimeOutboxService:
    @staticmethod
    def enqueue(
        session: Session,
        *,
        order_id: str,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> None:
        key = (idempotency_key or "").strip() or None
        if key:
            existing = session.exec(
                select(OrderRealtimeOutbox.id).where(
                    OrderRealtimeOutbox.order_id == order_id,
                    OrderRealtimeOutbox.event_type == event_type,
                    OrderRealtimeOutbox.idempotency_key == key,
                )
            ).first()
            if existing:
                return

        now = datetime.utcnow()
        payload_json = json.dumps(payload, default=str, separators=(",", ":"))
        session.add(
            OrderRealtimeOutbox(
                order_id=order_id,
                event_type=event_type,
                payload=payload_json,
                status="pending",
                attempt_count=0,
                max_attempts=max(1, int(settings.ORDER_REALTIME_OUTBOX_MAX_ATTEMPTS)),
                idempotency_key=key,
                created_at=now,
                updated_at=now,
                next_attempt_at=now,
            )
        )

    @staticmethod
    def _publish_payload(raw_payload: str) -> tuple[bool, str | None]:
        redis_client = RedisService.get_client()
        if redis_client is None:
            return False, "redis client unavailable"
        try:
            event = json.loads(raw_payload)
            redis_client.publish(ORDER_UPDATES_CHANNEL, json.dumps(event, default=str))
            return True, None
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _acquire_dispatch_lock() -> tuple[str | None, bool]:
        """
        Acquire a short-lived distributed lock for outbox dispatch.

        Returns:
          (token, lock_backend_checked)
          - token is set when lock acquired.
          - lock_backend_checked is True only when Redis was reachable and lock
            arbitration could be performed.
        """
        if not bool(getattr(settings, "ORDER_REALTIME_OUTBOX_USE_REDIS_DISPATCH_LOCK", True)):
            return None, False

        redis_client = RedisService.get_client()
        if redis_client is None:
            return None, False

        token = uuid.uuid4().hex
        ttl_seconds = max(1, int(getattr(settings, "ORDER_REALTIME_OUTBOX_DISPATCH_LOCK_TTL_SECONDS", 10)))
        try:
            acquired = redis_client.set(
                ORDER_DISPATCH_LOCK_KEY,
                token,
                ex=ttl_seconds,
                nx=True,
            )
            return (token if acquired else None), True
        except Exception as exc:
            logger.warning("Failed to acquire order outbox dispatch lock: %s", exc)
            return None, False

    @staticmethod
    def _release_dispatch_lock(token: str) -> None:
        redis_client = RedisService.get_client()
        if redis_client is None:
            return
        # Delete only when this process still owns the lock token.
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] "
            "then return redis.call('del', KEYS[1]) "
            "else return 0 end"
        )
        try:
            redis_client.eval(script, 1, ORDER_DISPATCH_LOCK_KEY, token)
        except Exception as exc:
            logger.warning("Failed to release order outbox dispatch lock: %s", exc)

    @staticmethod
    def dispatch_pending_once(*, max_rows: int | None = None) -> dict[str, int]:
        if not settings.ORDER_REALTIME_OUTBOX_ENABLED:
            return {
                "claimed": 0,
                "published": 0,
                "failed": 0,
                "lock_backend_checked": 0,
                "lock_backend_available": 0,
                "lock_state_code": 0,
            }

        claimed = 0
        published = 0
        failed = 0
        lock_token: str | None = None
        lock_checked = False
        lock_state = "none"
        now = datetime.utcnow()
        batch_size = max(1, int(max_rows or settings.ORDER_REALTIME_OUTBOX_BATCH_SIZE))
        max_retry_delay = max(1, int(settings.ORDER_REALTIME_OUTBOX_MAX_RETRY_DELAY_SECONDS))

        try:
            lock_token, lock_checked = OrderRealtimeOutboxService._acquire_dispatch_lock()
            # Another process currently owns dispatch responsibility.
            if lock_checked and lock_token is None:
                return {
                    "claimed": 0,
                    "published": 0,
                    "failed": 0,
                    "lock_backend_checked": 1,
                    "lock_backend_available": 1,
                    "lock_state_code": 1,  # held_elsewhere
                }
            if lock_checked:
                lock_state = "acquired" if lock_token else "held_elsewhere"
            else:
                lock_state = "backend_unavailable"

            with Session(engine) as session:
                query = (
                    select(OrderRealtimeOutbox)
                    .where(
                        OrderRealtimeOutbox.status.in_(PENDING_STATUSES),
                        OrderRealtimeOutbox.attempt_count < OrderRealtimeOutbox.max_attempts,
                        func.coalesce(
                            OrderRealtimeOutbox.next_attempt_at,
                            datetime(1970, 1, 1),
                        )
                        <= now,
                    )
                    .order_by(OrderRealtimeOutbox.created_at.asc(), OrderRealtimeOutbox.id.asc())
                    .limit(batch_size)
                )

                bind = session.get_bind()
                if bind is not None and bind.dialect.name == "postgresql":
                    query = query.with_for_update(skip_locked=True)

                rows = session.exec(query).all()
                if not rows:
                    return {
                        "claimed": 0,
                        "published": 0,
                        "failed": 0,
                        "lock_backend_checked": int(lock_checked),
                        "lock_backend_available": int(lock_checked),
                        "lock_state_code": 2 if lock_state == "backend_unavailable" else 0,
                    }

                claimed = len(rows)
                for row in rows:
                    row.status = "processing"
                    row.attempt_count += 1
                    row.updated_at = now
                    session.add(row)

                session.flush()

                for row in rows:
                    ok, error_text = OrderRealtimeOutboxService._publish_payload(row.payload)
                    row.updated_at = datetime.utcnow()
                    if ok:
                        row.status = "published"
                        row.published_at = datetime.utcnow()
                        row.next_attempt_at = None
                        row.last_error = None
                        published += 1
                    else:
                        row.status = "failed"
                        delay_seconds = min(max_retry_delay, 2 ** min(row.attempt_count, 8))
                        row.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
                        row.last_error = (error_text or "publish failed")[:1000]
                        failed += 1
                    session.add(row)

                session.commit()
        finally:
            if lock_token:
                OrderRealtimeOutboxService._release_dispatch_lock(lock_token)

        if claimed:
            logger.info(
                "Order realtime outbox dispatch completed claimed=%s published=%s failed=%s",
                claimed,
                published,
                failed,
            )
        return {
            "claimed": claimed,
            "published": published,
            "failed": failed,
            "lock_backend_checked": int(lock_checked),
            "lock_backend_available": int(lock_checked),
            "lock_state_code": 2 if lock_state == "backend_unavailable" else 0,
        }
