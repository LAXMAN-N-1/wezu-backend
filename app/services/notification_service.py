import json
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from app.core.config import settings
from app.core.logging import get_logger
from app.models.notification import Notification, NotificationStatus
from app.models.user import User
from app.services.email_service import EmailService
from app.services.event_stream_service import EventStreamService
from app.services.sms_service import SMSService
from sqlmodel import Session, select

logger = get_logger(__name__)


class NotificationService:
    VALID_CHANNELS = {"push", "email", "sms", "whatsapp"}
    DEFAULT_PREFERENCES = {
        "email": {
            "enabled": True,
            "rental_confirmations": True,
            "payment_receipts": True,
            "promotional": False,
            "security_alerts": True,
        },
        "sms": {
            "enabled": True,
            "rental_confirmations": True,
            "payment_receipts": False,
            "otp": True,
        },
        "push": {
            "enabled": True,
            "battery_available": True,
            "payment_reminders": True,
            "promotional": False,
        },
        "quiet_hours": {
            "enabled": False,
            "start_time": "22:00",
            "end_time": "07:00",
            "timezone": "UTC",
        },
    }

    @staticmethod
    def _normalize_app_scope(app_scope: Optional[str]) -> Optional[str]:
        if app_scope is None:
            return None
        normalized = str(app_scope).strip().lower().replace("-", "_").replace(" ", "_")
        return normalized or None

    @staticmethod
    def _set_status(notification: Notification, status: str) -> None:
        if not NotificationStatus.is_valid(status):
            raise ValueError(f"Unsupported notification status '{status}'")
        notification.status = status

    @staticmethod
    def send_notification(
        db: Session,
        user: User,
        title: str,
        message: str,
        type: str = "info",
        channel: str = "push",
        payload: Optional[str] = None,
        category: str = "transactional",
        bypass_preferences: bool = False,
        defer_delivery: bool = False,
        scheduled_at: Optional[datetime] = None,
        app_scope: Optional[str] = None,
    ) -> Notification:
        if user.id is None:
            raise ValueError("Cannot send notification to user without id")

        normalized_channel = channel.strip().lower()
        if normalized_channel not in NotificationService.VALID_CHANNELS:
            raise ValueError(
                f"Unsupported notification channel '{channel}'. "
                f"Allowed: {sorted(NotificationService.VALID_CHANNELS)}"
            )

        normalized_app_scope = NotificationService._normalize_app_scope(app_scope)
        notif = Notification(
            user_id=user.id,
            title=title,
            message=message,
            type=type,
            channel=normalized_channel,
            app_scope=normalized_app_scope,
            payload=payload,
            status=NotificationStatus.PENDING,
        )

        should_deliver, _reason = NotificationService._is_delivery_allowed(
            user=user,
            channel=normalized_channel,
            category=category,
            bypass_preferences=bypass_preferences,
        )
        if not should_deliver:
            logger.info(
                "notification.skipped",
                user_id=user.id,
                channel=normalized_channel,
                reason=_reason,
            )
            NotificationService._set_status(notif, NotificationStatus.SKIPPED)
            db.add(notif)
            db.commit()
            db.refresh(notif)
            return notif

        if defer_delivery:
            NotificationService._set_status(notif, NotificationStatus.QUEUED)
            notif.scheduled_at = scheduled_at or datetime.utcnow()
            db.add(notif)
            if hasattr(db, "flush"):
                db.flush()

            if notif.id is not None and bool(getattr(settings, "NOTIFICATION_OUTBOX_ENABLED", True)):
                from app.services.notification_outbox_service import NotificationOutboxService

                NotificationOutboxService.enqueue(
                    db,
                    notification=notif,
                    scheduled_at=notif.scheduled_at,
                    idempotency_key=f"notification:{notif.id}",
                )

            db.commit()
            db.refresh(notif)
            if (
                getattr(settings, "ENABLE_EVENT_STREAMS", True)
                and getattr(settings, "NOTIFICATION_QUEUE_ENABLED", False)
                and notif.scheduled_at <= datetime.utcnow()
            ):
                event = EventStreamService.build_event(
                    event_type="notification.dispatch.v1",
                    source="notification_service",
                    payload={
                        "notification_id": notif.id,
                        "user_id": user.id,
                    },
                    idempotency_key=f"notification:{notif.id}",
                )
                queue_id = EventStreamService.publish(settings.NOTIFICATION_STREAM_NAME, event)
                if queue_id is None and getattr(settings, "NOTIFICATION_QUEUE_REQUIRED", False):
                    logger.warning("notification.queue_unavailable", notification_id=notif.id)
            return notif

        delivered = NotificationService._dispatch(
            db=db,
            user=user,
            channel=normalized_channel,
            title=title,
            message=message,
            payload=payload,
            type=type,
            app_scope=normalized_app_scope,
        )
        if not delivered:
            logger.warning(
                "notification.delivery_failed",
                user_id=user.id,
                channel=normalized_channel,
                type=type,
            )
        NotificationService._set_status(
            notif,
            NotificationStatus.SENT if delivered else NotificationStatus.FAILED,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif

    @staticmethod
    def _dispatch(
        *,
        db: Session,
        user: User,
        channel: str,
        title: str,
        message: str,
        payload: Optional[str],
        type: str,
        app_scope: Optional[str] = None,
    ) -> bool:
        if channel == "push":
            from app.models.device import Device
            from app.services.fcm_service import FCMService

            query = select(Device).where(
                Device.user_id == user.id,
                Device.is_active == True,  # noqa: E712
            )
            normalized_app_scope = NotificationService._normalize_app_scope(app_scope)
            if normalized_app_scope:
                query = query.where(Device.app_scope == normalized_app_scope)
            devices = db.exec(query).all()
            tokens = sorted({device.fcm_token for device in devices if device.fcm_token})
            if not tokens:
                return False

            return FCMService.send_multicast(
                tokens,
                title,
                message,
                data={"type": type, "payload": payload or ""},
            )

        if channel == "email":
            if not user.email:
                return False
            return EmailService.send_email(user.email, title, message)

        if channel == "sms":
            if not user.phone_number:
                return False
            return SMSService.send_sms(user.phone_number, message)

        if channel == "whatsapp":
            if not user.phone_number:
                return False
            whatsapp_enabled = getattr(settings, "WHATSAPP_PROVIDER_ENABLED", False)
            if not whatsapp_enabled:
                logger.info(
                    "notification.whatsapp_skipped",
                    user_id=user.id,
                    title=title[:50],
                )
                return False
            # When enabled, dispatch via the configured WhatsApp provider
            # (e.g. Twilio, Gupshup).  For now, log the intent.
            logger.info(
                "notification.whatsapp_dispatched",
                user_id=user.id,
                phone_prefix=user.phone_number[:6],
                title=title[:50],
            )
            return True

        return False

    @staticmethod
    def _is_delivery_allowed(
        *,
        user: User,
        channel: str,
        category: str,
        bypass_preferences: bool,
    ) -> Tuple[bool, str]:
        if bypass_preferences:
            return True, "bypass_preferences"

        prefs = NotificationService._load_preferences(user.notification_preferences)
        channel_prefs = prefs.get(channel, {})

        if not channel_prefs.get("enabled", True):
            return False, f"{channel}_disabled"

        category_flag = NotificationService._resolve_category_flag(channel, category)
        if category_flag and not channel_prefs.get(category_flag, True):
            return False, f"{channel}_{category_flag}_disabled"

        if NotificationService._is_within_quiet_hours(prefs.get("quiet_hours", {})):
            if category not in {"transactional", "security", "otp"}:
                return False, "quiet_hours"

        return True, "allowed"

    @staticmethod
    def _load_preferences(raw_preferences: Optional[str]) -> Dict[str, Dict[str, Any]]:
        defaults = json.loads(json.dumps(NotificationService.DEFAULT_PREFERENCES))
        if not raw_preferences:
            return defaults

        try:
            loaded = raw_preferences if isinstance(raw_preferences, dict) else json.loads(raw_preferences)
            if not isinstance(loaded, dict):
                return defaults
            for section in ["email", "sms", "push", "quiet_hours"]:
                section_value = loaded.get(section)
                if isinstance(section_value, dict):
                    defaults[section].update(section_value)
        except (json.JSONDecodeError, TypeError):
            return defaults
        return defaults

    @staticmethod
    def _resolve_category_flag(channel: str, category: str) -> Optional[str]:
        normalized_category = category.strip().lower().replace("-", "_")
        if channel == "email":
            return {
                "promotional": "promotional",
                "payment": "payment_receipts",
                "rental": "rental_confirmations",
                "security": "security_alerts",
            }.get(normalized_category)
        if channel == "sms":
            return {
                "payment": "payment_receipts",
                "rental": "rental_confirmations",
                "otp": "otp",
            }.get(normalized_category)
        if channel == "push":
            return {
                "promotional": "promotional",
                "battery_alert": "battery_available",
                "payment": "payment_reminders",
            }.get(normalized_category)
        return None

    @staticmethod
    def _is_within_quiet_hours(quiet_hours: Dict[str, Any]) -> bool:
        if not quiet_hours.get("enabled", False):
            return False

        start_raw = quiet_hours.get("start_time", "22:00")
        end_raw = quiet_hours.get("end_time", "07:00")
        timezone_name = quiet_hours.get("timezone", "UTC")

        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = ZoneInfo("UTC")

        try:
            start_hour, start_minute = [int(part) for part in str(start_raw).split(":", 1)]
            end_hour, end_minute = [int(part) for part in str(end_raw).split(":", 1)]
            if not (0 <= start_hour <= 23 and 0 <= start_minute <= 59):
                return False
            if not (0 <= end_hour <= 23 and 0 <= end_minute <= 59):
                return False
            start = time(hour=start_hour, minute=start_minute)
            end = time(hour=end_hour, minute=end_minute)
        except Exception:
            return False

        now_local = datetime.now(tz).time()
        if start <= end:
            return start <= now_local <= end
        return now_local >= start or now_local <= end

    @staticmethod
    def schedule_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        scheduled_at: datetime,
        channel: str = "push",
    ) -> Notification:
        user = db.get(User, user_id)
        if not user:
            raise ValueError(f"user_id={user_id} not found for schedule_notification")
        return NotificationService.send_notification(
            db=db,
            user=user,
            title=title,
            message=message,
            type="info",
            channel=channel,
            category="transactional",
            bypass_preferences=False,
            defer_delivery=True,
            scheduled_at=scheduled_at,
        )

    @staticmethod
    def enqueue_notification(
        db: Session,
        *,
        user: User,
        title: str,
        message: str,
        type: str = "info",
        channel: str = "push",
        payload: Optional[str] = None,
        category: str = "transactional",
        bypass_preferences: bool = False,
        scheduled_at: Optional[datetime] = None,
    ) -> Notification:
        return NotificationService.send_notification(
            db=db,
            user=user,
            title=title,
            message=message,
            type=type,
            channel=channel,
            payload=payload,
            category=category,
            bypass_preferences=bypass_preferences,
            defer_delivery=True,
            scheduled_at=scheduled_at,
        )

    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        unread_only: bool = False,
        app_scope: Optional[str] = None,
        include_global: bool = True,
    ) -> List[Notification]:
        statement = select(Notification).where(Notification.user_id == user_id)
        normalized_app_scope = NotificationService._normalize_app_scope(app_scope)
        if normalized_app_scope:
            if include_global:
                statement = statement.where(
                    or_(
                        Notification.app_scope == normalized_app_scope,
                        Notification.app_scope.is_(None),
                    )
                )
            else:
                statement = statement.where(Notification.app_scope == normalized_app_scope)
        if unread_only:
            statement = statement.where(Notification.is_read == False)  # noqa: E712
        statement = statement.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        return db.exec(statement).all()

    @staticmethod
    def mark_read(db: Session, notification_id: int, user_id: int):
        notif = db.get(Notification, notification_id)
        if notif and notif.user_id == user_id:
            notif.is_read = True
            db.add(notif)
            db.commit()
            db.refresh(notif)
        return notif

    # ── P1-A-5: Missing service methods ───────────────────────────────────

    @staticmethod
    def clear_all_notifications(db: Session, user_id: int) -> int:
        """Delete all notifications for a user. Returns count deleted."""
        notifications = db.exec(
            select(Notification).where(Notification.user_id == user_id)
        ).all()
        count = len(notifications)
        for notif in notifications:
            db.delete(notif)
        if count:
            db.commit()
        return count

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """Count unread notifications for a user."""
        from sqlalchemy import func as sa_func

        result = db.exec(
            select(sa_func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        ).one()
        return result or 0

    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        """Mark all unread notifications as read. Returns count updated."""
        unread = db.exec(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        ).all()
        count = len(unread)
        for notif in unread:
            notif.is_read = True
            db.add(notif)
        if count:
            db.commit()
        return count

    @staticmethod
    def send_bulk_notification(
        db: Session,
        segment: str,
        title: str,
        message: str,
        type: str = "info",
        channel: str = "push",
    ) -> int:
        """Send a notification to a user segment. Returns count sent."""
        if segment == "all":
            users = db.exec(
                select(User).where(User.is_active == True).limit(10000)  # noqa: E712
            ).all()
        else:
            # Future: filter by segment (e.g. "dealers", "new_users_7d")
            users = db.exec(
                select(User).where(User.is_active == True).limit(10000)  # noqa: E712
            ).all()

        sent = 0
        for user in users:
            try:
                NotificationService.send_notification(
                    db,
                    user,
                    title=title,
                    message=message,
                    type=type,
                    channel=channel,
                    category="promotional",
                    bypass_preferences=False,
                )
                sent += 1
            except Exception:
                logger.warning("notification.bulk_failed", user_id=user.id, exc_info=True)
        return sent

    @staticmethod
    def process_pending_scheduled_notifications(
        db: Session,
        *,
        limit: int = 200,
    ) -> Dict[str, int]:
        if not bool(getattr(settings, "NOTIFICATION_OUTBOX_ENABLED", True)):
            now = datetime.utcnow()
            notifications = db.exec(
                select(Notification)
                .where(Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.QUEUED]))
                .where(Notification.scheduled_at.is_not(None))
                .where(Notification.scheduled_at <= now)
                .order_by(Notification.scheduled_at.asc(), Notification.id.asc())
                .limit(limit)
            ).all()

            processed = 0
            sent = 0
            failed = 0
            skipped = 0

            for notif in notifications:
                processed += 1
                user = db.get(User, notif.user_id)
                if not user:
                    NotificationService._set_status(notif, NotificationStatus.FAILED)
                    db.add(notif)
                    failed += 1
                    continue

                channel = (notif.channel or "push").strip().lower()
                if notif.status != NotificationStatus.QUEUED:
                    should_deliver, _reason = NotificationService._is_delivery_allowed(
                        user=user,
                        channel=channel,
                        category="transactional",
                        bypass_preferences=False,
                    )
                    if not should_deliver:
                        NotificationService._set_status(notif, NotificationStatus.SKIPPED)
                        db.add(notif)
                        skipped += 1
                        continue

                delivered = NotificationService._dispatch(
                    db=db,
                    user=user,
                    channel=channel,
                    title=notif.title,
                    message=notif.message,
                    payload=notif.payload,
                    type=notif.type,
                    app_scope=notif.app_scope,
                )
                NotificationService._set_status(
                    notif,
                    NotificationStatus.SENT if delivered else NotificationStatus.FAILED,
                )
                db.add(notif)
                if delivered:
                    sent += 1
                else:
                    failed += 1

            if processed > 0:
                db.commit()

            return {
                "processed": processed,
                "sent": sent,
                "failed": failed,
                "skipped": skipped,
            }

        from app.services.notification_outbox_service import NotificationOutboxService

        now = datetime.utcnow()
        due_notifications = db.exec(
            select(Notification)
            .where(Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.QUEUED]))
            .where(Notification.scheduled_at.is_not(None))
            .where(Notification.scheduled_at <= now)
            .order_by(Notification.scheduled_at.asc(), Notification.id.asc())
            .limit(limit)
        ).all()

        enqueued = 0
        for notification in due_notifications:
            if notification.status == NotificationStatus.PENDING:
                NotificationService._set_status(notification, NotificationStatus.QUEUED)
                db.add(notification)
            NotificationOutboxService.enqueue(
                db,
                notification=notification,
                scheduled_at=notification.scheduled_at,
                idempotency_key=f"notification:{notification.id}",
            )
            enqueued += 1

        if enqueued:
            db.commit()

        dispatch = NotificationOutboxService.dispatch_pending_once(max_rows=limit)
        return {
            "processed": int(dispatch.get("claimed", 0)),
            "sent": int(dispatch.get("published", 0)),
            "failed": int(dispatch.get("failed", 0)) + int(dispatch.get("dead_letter", 0)),
            "skipped": 0,
            "dead_letter": int(dispatch.get("dead_letter", 0)),
            "enqueued": enqueued,
        }
