from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import engine
from app.models.notification import Notification, NotificationStatus
from app.models.notification_outbox import NotificationOutbox, NotificationOutboxStatus
from app.models.user import User

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {
    NotificationOutboxStatus.PENDING,
    NotificationOutboxStatus.FAILED,
}


class NotificationOutboxService:
    @staticmethod
    def enqueue(
        session: Session,
        *,
        notification: Notification,
        scheduled_at: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> NotificationOutbox:
        if notification.id is None:
            raise ValueError("notification.id is required before enqueue")

        key = (idempotency_key or "").strip() or None
        if key:
            existing = session.exec(
                select(NotificationOutbox).where(
                    NotificationOutbox.notification_id == notification.id,
                    NotificationOutbox.idempotency_key == key,
                )
            ).first()
            if existing:
                return existing

        now = datetime.utcnow()
        due_at = scheduled_at or notification.scheduled_at or now
        row = NotificationOutbox(
            notification_id=notification.id,
            user_id=notification.user_id,
            channel=(notification.channel or "push").strip().lower(),
            status=NotificationOutboxStatus.PENDING,
            attempt_count=0,
            max_attempts=max(1, int(getattr(settings, "NOTIFICATION_OUTBOX_MAX_ATTEMPTS", 8))),
            idempotency_key=key or f"notification:{notification.id}",
            created_at=now,
            updated_at=now,
            next_attempt_at=due_at,
        )
        session.add(row)
        return row

    @staticmethod
    def _next_retry_eta(attempt_count: int) -> datetime:
        max_delay = max(1, int(getattr(settings, "NOTIFICATION_OUTBOX_MAX_RETRY_DELAY_SECONDS", 300)))
        delay_seconds = min(max_delay, 2 ** min(max(1, attempt_count), 8))
        return datetime.utcnow() + timedelta(seconds=delay_seconds)

    @staticmethod
    def _claim_rows(
        session: Session,
        *,
        now: datetime,
        batch_size: int,
        notification_id: int | None = None,
    ) -> list[NotificationOutbox]:
        query = (
            select(NotificationOutbox)
            .where(
                NotificationOutbox.status.in_(tuple(_RETRYABLE_STATUSES)),
                NotificationOutbox.attempt_count < NotificationOutbox.max_attempts,
                or_(
                    NotificationOutbox.next_attempt_at.is_(None),
                    NotificationOutbox.next_attempt_at <= now,
                ),
            )
            .order_by(NotificationOutbox.created_at.asc(), NotificationOutbox.id.asc())
            .limit(max(1, batch_size))
        )
        if notification_id is not None:
            query = query.where(NotificationOutbox.notification_id == notification_id)

        bind = session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)

        rows = session.exec(query).all()
        if not rows:
            return []

        for row in rows:
            row.status = NotificationOutboxStatus.PROCESSING
            row.attempt_count += 1
            row.updated_at = now
            session.add(row)
        session.flush()
        return rows

    @staticmethod
    def _handle_terminal_without_send(
        *,
        outbox_row: NotificationOutbox,
        notification: Notification,
    ) -> str:
        if notification.status in {NotificationStatus.SENT, NotificationStatus.SKIPPED}:
            outbox_row.status = NotificationOutboxStatus.PUBLISHED
            outbox_row.published_at = datetime.utcnow()
            outbox_row.next_attempt_at = None
            outbox_row.last_error = None
            return "published"

        outbox_row.status = NotificationOutboxStatus.DEAD_LETTER
        outbox_row.next_attempt_at = None
        outbox_row.last_error = f"notification reached terminal status={notification.status}"
        return "dead_letter"

    @staticmethod
    def _dispatch_claimed_row(session: Session, row: NotificationOutbox, now: datetime) -> str:
        notification = session.get(Notification, row.notification_id)
        if not notification:
            row.status = NotificationOutboxStatus.DEAD_LETTER
            row.next_attempt_at = None
            row.last_error = "notification row not found"
            row.updated_at = now
            session.add(row)
            return "dead_letter"

        if notification.status in {
            NotificationStatus.SENT,
            NotificationStatus.SKIPPED,
            NotificationStatus.DEAD_LETTER,
        }:
            result = NotificationOutboxService._handle_terminal_without_send(
                outbox_row=row,
                notification=notification,
            )
            row.updated_at = datetime.utcnow()
            session.add(row)
            return result

        if notification.scheduled_at and notification.scheduled_at > now:
            row.status = NotificationOutboxStatus.PENDING
            row.next_attempt_at = notification.scheduled_at
            row.last_error = None
            row.updated_at = now
            session.add(row)
            return "deferred"

        user = session.get(User, notification.user_id)
        if not user:
            notification.status = NotificationStatus.FAILED
            session.add(notification)
            if row.attempt_count >= row.max_attempts:
                row.status = NotificationOutboxStatus.DEAD_LETTER
                notification.status = NotificationStatus.DEAD_LETTER
                row.next_attempt_at = None
                result = "dead_letter"
            else:
                row.status = NotificationOutboxStatus.FAILED
                row.next_attempt_at = NotificationOutboxService._next_retry_eta(row.attempt_count)
                result = "failed"
            row.last_error = "user not found"
            row.updated_at = datetime.utcnow()
            session.add(row)
            session.add(notification)
            return result

        from app.services.notification_service import NotificationService

        delivered = NotificationService._dispatch(  # noqa: SLF001
            db=session,
            user=user,
            channel=(notification.channel or "push").strip().lower(),
            title=notification.title,
            message=notification.message,
            payload=notification.payload,
            type=notification.type,
            app_scope=notification.app_scope,
        )
        if delivered:
            notification.status = NotificationStatus.SENT
            row.status = NotificationOutboxStatus.PUBLISHED
            row.published_at = datetime.utcnow()
            row.next_attempt_at = None
            row.last_error = None
            result = "published"
        else:
            if row.attempt_count >= row.max_attempts:
                notification.status = NotificationStatus.DEAD_LETTER
                row.status = NotificationOutboxStatus.DEAD_LETTER
                row.next_attempt_at = None
                result = "dead_letter"
            else:
                notification.status = NotificationStatus.FAILED
                row.status = NotificationOutboxStatus.FAILED
                row.next_attempt_at = NotificationOutboxService._next_retry_eta(row.attempt_count)
                result = "failed"
            row.last_error = "provider delivery returned false"

        row.updated_at = datetime.utcnow()
        session.add(notification)
        session.add(row)
        return result

    @staticmethod
    def dispatch_pending_once(
        *,
        max_rows: int | None = None,
        notification_id: int | None = None,
    ) -> dict[str, int]:
        if not bool(getattr(settings, "NOTIFICATION_OUTBOX_ENABLED", True)):
            return {
                "claimed": 0,
                "published": 0,
                "failed": 0,
                "dead_letter": 0,
                "deferred": 0,
                "errored": 0,
            }

        claimed = 0
        published = 0
        failed = 0
        dead_letter = 0
        deferred = 0
        errored = 0
        now = datetime.utcnow()
        batch_size = max(1, int(max_rows or getattr(settings, "NOTIFICATION_OUTBOX_BATCH_SIZE", 200)))

        with Session(engine) as session:
            rows = NotificationOutboxService._claim_rows(
                session,
                now=now,
                batch_size=batch_size,
                notification_id=notification_id,
            )
            if not rows:
                return {
                    "claimed": 0,
                    "published": 0,
                    "failed": 0,
                    "dead_letter": 0,
                    "deferred": 0,
                    "errored": 0,
                }

            claimed = len(rows)
            for row in rows:
                try:
                    outcome = NotificationOutboxService._dispatch_claimed_row(session, row, now)
                except Exception as exc:  # defensive catch: do not abort whole batch
                    logger.exception("Notification outbox dispatch failed row_id=%s: %s", row.id, exc)
                    if row.attempt_count >= row.max_attempts:
                        row.status = NotificationOutboxStatus.DEAD_LETTER
                        row.next_attempt_at = None
                        dead_letter += 1
                    else:
                        row.status = NotificationOutboxStatus.FAILED
                        row.next_attempt_at = NotificationOutboxService._next_retry_eta(row.attempt_count)
                        failed += 1
                    row.last_error = str(exc)[:1000]
                    row.updated_at = datetime.utcnow()
                    session.add(row)
                    errored += 1
                    continue

                if outcome == "published":
                    published += 1
                elif outcome == "failed":
                    failed += 1
                elif outcome == "dead_letter":
                    dead_letter += 1
                elif outcome == "deferred":
                    deferred += 1

            session.commit()

        if claimed:
            logger.info(
                "Notification outbox dispatch claimed=%s published=%s failed=%s dead_letter=%s deferred=%s errored=%s",
                claimed,
                published,
                failed,
                dead_letter,
                deferred,
                errored,
            )
        return {
            "claimed": claimed,
            "published": published,
            "failed": failed,
            "dead_letter": dead_letter,
            "deferred": deferred,
            "errored": errored,
        }

    @staticmethod
    def dispatch_for_notification(notification_id: int) -> dict[str, int]:
        return NotificationOutboxService.dispatch_pending_once(
            max_rows=10,
            notification_id=notification_id,
        )

    @staticmethod
    def get_health_snapshot() -> dict[str, Any]:
        try:
            with Session(engine) as session:
                pending_count = int(
                    session.exec(
                        select(func.count(NotificationOutbox.id)).where(
                            NotificationOutbox.status.in_(
                                (
                                    NotificationOutboxStatus.PENDING,
                                    NotificationOutboxStatus.FAILED,
                                )
                            )
                        )
                    ).one()
                )
                dead_letter_count = int(
                    session.exec(
                        select(func.count(NotificationOutbox.id)).where(
                            NotificationOutbox.status == NotificationOutboxStatus.DEAD_LETTER
                        )
                    ).one()
                )
                oldest_pending_created_at = session.exec(
                    select(func.min(NotificationOutbox.created_at)).where(
                        NotificationOutbox.status.in_(
                            (
                                NotificationOutboxStatus.PENDING,
                                NotificationOutboxStatus.FAILED,
                            )
                        )
                    )
                ).one()

            oldest_age_seconds = None
            if oldest_pending_created_at:
                oldest_age_seconds = max(
                    0,
                    int((datetime.utcnow() - oldest_pending_created_at).total_seconds()),
                )
            return {
                "status": "ready",
                "pending_count": pending_count,
                "dead_letter_count": dead_letter_count,
                "oldest_pending_age_seconds": oldest_age_seconds,
                "slo_max_pending_count": int(
                    getattr(settings, "NOTIFICATION_OUTBOX_SLO_MAX_PENDING_COUNT", 5000)
                ),
                "slo_max_oldest_pending_age_seconds": int(
                    getattr(settings, "NOTIFICATION_OUTBOX_SLO_MAX_OLDEST_PENDING_AGE_SECONDS", 300)
                ),
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "details": str(exc),
            }
