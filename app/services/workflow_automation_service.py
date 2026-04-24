from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.models.notification import Notification
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class WorkflowAutomationService:
    """Centralized automatic workflow notifications for business events."""

    INTERNAL_AUTOMATION_ROLES = frozenset(
        {
            "admin",
            "super_admin",
            "support",
            "staff",
            "operations",
            "ops_manager",
            "finance",
        }
    )
    DEFAULT_DEDUPE_MINUTES = 60
    LOGISTICS_APP_SCOPE = "logistics"

    @staticmethod
    def _money(value: Decimal | float | int | str) -> str:
        try:
            return f"{Decimal(str(value)).quantize(Decimal('0.01'))}"
        except Exception:
            return str(value)

    @staticmethod
    def _dedupe_exists(
        db: Session,
        *,
        user_id: int,
        channel: str,
        notification_type: str,
        title: str,
        message: str,
        window_minutes: int,
    ) -> bool:
        if window_minutes <= 0:
            return False
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        existing = db.exec(
            select(Notification.id)
            .where(Notification.user_id == user_id)
            .where(Notification.channel == channel)
            .where(Notification.type == notification_type)
            .where(Notification.title == title)
            .where(Notification.message == message)
            .where(Notification.status != "failed")
            .where(Notification.created_at >= cutoff)
            .limit(1)
        ).first()
        return existing is not None

    @staticmethod
    def _internal_ops_user_ids(db: Session) -> list[int]:
        role_names = tuple(sorted(WorkflowAutomationService.INTERNAL_AUTOMATION_ROLES))
        role_user_ids = db.exec(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(func.lower(Role.name).in_(role_names))
            .where(User.is_active == True)  # noqa: E712
            .where(User.is_deleted == False)  # noqa: E712
        ).all()

        superuser_ids = db.exec(
            select(User.id)
            .where(User.is_superuser == True)  # noqa: E712
            .where(User.is_active == True)  # noqa: E712
            .where(User.is_deleted == False)  # noqa: E712
        ).all()

        user_ids = {int(user_id) for user_id in [*role_user_ids, *superuser_ids] if user_id is not None}
        return sorted(user_ids)

    @staticmethod
    def _notify_internal_ops(
        db: Session,
        *,
        title: str,
        message: str,
        notification_type: str,
        channels: Iterable[str] = ("push", "email"),
        category: str = "operational",
        dedupe_window_minutes: int | None = None,
        exclude_user_ids: Iterable[int] | None = None,
        app_scope: str | None = None,
    ) -> bool:
        excluded = {int(user_id) for user_id in (exclude_user_ids or [])}
        sent_any = False
        for user_id in WorkflowAutomationService._internal_ops_user_ids(db):
            if user_id in excluded:
                continue
            sent_any = (
                WorkflowAutomationService._notify_channels(
                    db,
                    user_id=user_id,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    channels=channels,
                    category=category,
                    bypass_preferences=True,
                    dedupe_window_minutes=dedupe_window_minutes,
                    app_scope=app_scope,
                )
                or sent_any
            )
        return sent_any

    @staticmethod
    def _notify_channels(
        db: Session,
        *,
        user_id: int,
        title: str,
        message: str,
        notification_type: str,
        channels: Iterable[str],
        category: str = "transactional",
        bypass_preferences: bool = False,
        payload: str | None = None,
        dedupe_window_minutes: int | None = None,
        app_scope: str | None = None,
    ) -> bool:
        user = db.get(User, user_id)
        if not user:
            logger.warning("Workflow notification skipped: user_id=%s not found", user_id)
            return False

        sent_any = False
        dedupe_window = (
            WorkflowAutomationService.DEFAULT_DEDUPE_MINUTES
            if dedupe_window_minutes is None
            else max(0, int(dedupe_window_minutes))
        )
        for channel in channels:
            channel_name = (channel or "").strip().lower()
            if not channel_name:
                continue
            if WorkflowAutomationService._dedupe_exists(
                db,
                user_id=user_id,
                channel=channel_name,
                notification_type=notification_type,
                title=title,
                message=message,
                window_minutes=dedupe_window,
            ):
                continue
            try:
                notif = NotificationService.send_notification(
                    db=db,
                    user=user,
                    title=title,
                    message=message,
                    type=notification_type,
                    channel=channel_name,
                    category=category,
                    bypass_preferences=bypass_preferences,
                    payload=payload,
                    defer_delivery=bool(getattr(settings, "ASYNC_WORKFLOW_NOTIFICATIONS", True)),
                    app_scope=app_scope,
                )
                if notif.status in {"sent", "queued"}:
                    sent_any = True
            except Exception:
                logger.exception(
                    "Workflow notification failed user_id=%s channel=%s type=%s",
                    user_id,
                    channel_name,
                    notification_type,
                )
        return sent_any

    @staticmethod
    def notify_wallet_recharge_captured(
        db: Session,
        *,
        user_id: int,
        amount: Decimal | float | int | str,
        payment_id: str,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Wallet Recharge Successful",
            message=f"We have credited INR {amount_text} to your wallet. Payment reference: {payment_id}.",
            notification_type="wallet_recharge_success",
            channels=("push", "email", "sms"),
            category="payment",
            dedupe_window_minutes=30,
        )

    @staticmethod
    def notify_wallet_recharge_initiated(
        db: Session,
        *,
        user_id: int,
        amount: Decimal | float | int | str,
        order_id: str,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Wallet Recharge Initiated",
            message=(
                f"Your recharge request for INR {amount_text} was created. "
                f"Complete payment for order {order_id} to credit your wallet."
            ),
            notification_type="wallet_recharge_initiated",
            channels=("push",),
            category="payment",
            dedupe_window_minutes=30,
        )

    @staticmethod
    def notify_wallet_recharge_failed(
        db: Session,
        *,
        user_id: int,
        order_id: str,
        payment_id: str | None = None,
    ) -> bool:
        suffix = f" Payment reference: {payment_id}." if payment_id else ""
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Wallet Recharge Failed",
            message=f"Your wallet recharge for order {order_id} failed.{suffix} No amount was credited.",
            notification_type="wallet_recharge_failed",
            channels=("push", "sms"),
            category="payment",
            dedupe_window_minutes=30,
        )

    @staticmethod
    def notify_withdrawal_requested(
        db: Session,
        *,
        user_id: int,
        request_id: int,
        amount: Decimal | float | int | str,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Withdrawal Request Submitted",
            message=(
                f"Your withdrawal request #{request_id} for INR {amount_text} was submitted "
                "and is awaiting approval."
            ),
            notification_type="withdrawal_requested",
            channels=("push", "email"),
            category="payment",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_withdrawal_processed(
        db: Session,
        *,
        user_id: int,
        request_id: int,
        amount: Decimal | float | int | str,
        payout_reference: str | None = None,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        ref_text = f" Payout reference: {payout_reference}." if payout_reference else ""
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Withdrawal Processed",
            message=f"Your withdrawal request #{request_id} for INR {amount_text} has been processed.{ref_text}",
            notification_type="withdrawal_processed",
            channels=("push", "email", "sms"),
            category="payment",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_withdrawal_rejected(
        db: Session,
        *,
        user_id: int,
        request_id: int,
        amount: Decimal | float | int | str,
        reason: str | None = None,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        reason_text = f" Reason: {reason}" if reason else ""
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Withdrawal Rejected",
            message=(
                f"Your withdrawal request #{request_id} for INR {amount_text} was rejected and "
                f"the amount has been restored to your wallet.{reason_text}"
            ),
            notification_type="withdrawal_rejected",
            channels=("push", "email", "sms"),
            category="payment",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_rental_confirmed(
        db: Session,
        *,
        user_id: int,
        rental_id: int,
        amount: Decimal | float | int | str,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Rental Confirmed",
            message=f"Rental #{rental_id} is now active. Payment of INR {amount_text} was verified successfully.",
            notification_type="rental_confirmed",
            channels=("push", "sms"),
            category="rental",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_rental_payment_order_created(
        db: Session,
        *,
        user_id: int,
        rental_id: int,
        amount: Decimal | float | int | str,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Complete Rental Payment",
            message=(
                f"Rental #{rental_id} is pending payment. "
                f"Please complete INR {amount_text} to activate your rental."
            ),
            notification_type="rental_payment_pending",
            channels=("push", "sms"),
            category="payment",
            dedupe_window_minutes=30,
        )

    @staticmethod
    def notify_rental_payment_reminder(
        db: Session,
        *,
        user_id: int,
        rental_id: int,
        amount: Decimal | float | int | str,
        minutes_left: int,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Rental Payment Reminder",
            message=(
                f"Rental #{rental_id} is still awaiting payment of INR {amount_text}. "
                f"Complete payment in {max(0, minutes_left)} minute(s) to avoid cancellation."
            ),
            notification_type="rental_payment_reminder",
            channels=("push", "sms"),
            category="payment",
            dedupe_window_minutes=15,
        )

    @staticmethod
    def notify_rental_payment_timeout_cancelled(
        db: Session,
        *,
        user_id: int,
        rental_id: int,
    ) -> bool:
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Rental Cancelled",
            message=(
                f"Rental #{rental_id} was cancelled because payment was not completed within the allowed window. "
                "You can create a new rental from the app."
            ),
            notification_type="rental_payment_timeout_cancelled",
            channels=("push", "sms"),
            category="rental",
            dedupe_window_minutes=120,
        )

    @staticmethod
    def notify_rental_return_completed(
        db: Session,
        *,
        user_id: int,
        rental_id: int,
        station_id: int,
    ) -> bool:
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Rental Completed",
            message=f"Rental #{rental_id} was completed successfully at station #{station_id}.",
            notification_type="rental_completed",
            channels=("push", "sms"),
            category="rental",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_rental_extension_reviewed(
        db: Session,
        *,
        user_id: int,
        extension_id: int,
        approved: bool,
    ) -> bool:
        decision = "approved" if approved else "rejected"
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Rental Extension Reviewed",
            message=f"Your rental extension request #{extension_id} has been {decision}.",
            notification_type="rental_extension_reviewed",
            channels=("push", "sms"),
            category="rental",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_rental_pause_reviewed(
        db: Session,
        *,
        user_id: int,
        pause_id: int,
        approved: bool,
    ) -> bool:
        decision = "approved" if approved else "rejected"
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Rental Pause Reviewed",
            message=f"Your rental pause request #{pause_id} has been {decision}.",
            notification_type="rental_pause_reviewed",
            channels=("push", "sms"),
            category="rental",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_late_fee_waiver_reviewed(
        db: Session,
        *,
        user_id: int,
        waiver_id: int,
        approved: bool,
    ) -> bool:
        decision = "approved" if approved else "rejected"
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Late Fee Waiver Reviewed",
            message=f"Your late fee waiver request #{waiver_id} has been {decision}.",
            notification_type="late_fee_waiver_reviewed",
            channels=("push", "sms"),
            category="payment",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_late_fee_assessed(
        db: Session,
        *,
        user_id: int,
        rental_id: int,
        total_late_fee: Decimal | float | int | str,
        days_overdue: int,
    ) -> bool:
        fee_text = WorkflowAutomationService._money(total_late_fee)
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Late Fee Applied",
            message=(
                f"Rental #{rental_id} is overdue by {days_overdue} day(s). "
                f"A late fee of INR {fee_text} has been applied."
            ),
            notification_type="late_fee_applied",
            channels=("push", "sms"),
            category="payment",
            dedupe_window_minutes=180,
        )

    @staticmethod
    def notify_order_refund_outcome(
        db: Session,
        *,
        user_id: int,
        order_id: str,
        amount: Decimal | float | int | str,
        success: bool,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        if success:
            title = "Refund Processed"
            message = f"Refund for order {order_id} of INR {amount_text} has been processed."
            event = "order_refund_processed"
        else:
            title = "Refund Failed"
            message = (
                f"Refund for order {order_id} of INR {amount_text} could not be completed automatically. "
                "Support has been notified."
            )
            event = "order_refund_failed"
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title=title,
            message=message,
            notification_type=event,
            channels=("push", "email", "sms"),
            category="payment",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_logistics_order_driver_assigned(
        db: Session,
        *,
        order_id: str,
        customer_user_id: int | None,
        driver_user_id: int | None,
        driver_display_name: str | None = None,
        scheduled_slot_start: datetime | None = None,
        scheduled_slot_end: datetime | None = None,
    ) -> bool:
        slot_text = ""
        if scheduled_slot_start and scheduled_slot_end:
            slot_text = (
                f" Delivery window: {scheduled_slot_start:%Y-%m-%d %H:%M} "
                f"to {scheduled_slot_end:%H:%M}."
            )
        driver_name = (driver_display_name or "").strip() or "your delivery partner"

        sent_any = False
        if customer_user_id is not None:
            sent_any = (
                WorkflowAutomationService._notify_channels(
                    db,
                    user_id=customer_user_id,
                    title="Driver Assigned",
                    message=(
                        f"{driver_name} has been assigned to order {order_id}.{slot_text} "
                        "You can track updates in the app."
                    ),
                    notification_type="logistics_driver_assigned_customer",
                    channels=("push", "sms"),
                    category="transactional",
                    dedupe_window_minutes=20,
                    app_scope=WorkflowAutomationService.LOGISTICS_APP_SCOPE,
                )
                or sent_any
            )

        if driver_user_id is not None:
            sent_any = (
                WorkflowAutomationService._notify_channels(
                    db,
                    user_id=driver_user_id,
                    title="New Delivery Assignment",
                    message=(
                        f"You have been assigned to order {order_id}.{slot_text} "
                        "Open the driver app for route and delivery instructions."
                    ),
                    notification_type="logistics_driver_assigned_driver",
                    channels=("push", "sms"),
                    category="operational",
                    bypass_preferences=True,
                    dedupe_window_minutes=20,
                    app_scope=WorkflowAutomationService.LOGISTICS_APP_SCOPE,
                )
                or sent_any
            )

        return sent_any

    @staticmethod
    def notify_logistics_order_created(
        db: Session,
        *,
        order_id: str,
        destination: str | None,
        customer_user_id: int | None = None,
        driver_user_id: int | None = None,
        scheduled_slot_start: datetime | None = None,
        scheduled_slot_end: datetime | None = None,
    ) -> bool:
        slot_text = ""
        if scheduled_slot_start and scheduled_slot_end:
            slot_text = (
                f" Delivery window: {scheduled_slot_start:%Y-%m-%d %H:%M} "
                f"to {scheduled_slot_end:%H:%M}."
            )
        destination_text = (destination or "").strip() or "assigned destination"

        sent_any = False
        if customer_user_id is not None:
            sent_any = (
                WorkflowAutomationService._notify_channels(
                    db,
                    user_id=customer_user_id,
                    title="Order Created",
                    message=(
                        f"Your order {order_id} to {destination_text} has been created.{slot_text} "
                        "Track updates in the logistics app."
                    ),
                    notification_type="logistics_order_created_customer",
                    channels=("push", "sms"),
                    category="transactional",
                    dedupe_window_minutes=20,
                    app_scope=WorkflowAutomationService.LOGISTICS_APP_SCOPE,
                )
                or sent_any
            )

        if driver_user_id is not None:
            sent_any = (
                WorkflowAutomationService._notify_channels(
                    db,
                    user_id=driver_user_id,
                    title="New Delivery Assignment",
                    message=(
                        f"Order {order_id} has been assigned to you for {destination_text}.{slot_text} "
                        "Open the logistics app for next steps."
                    ),
                    notification_type="logistics_order_created_driver",
                    channels=("push", "sms"),
                    category="operational",
                    bypass_preferences=True,
                    dedupe_window_minutes=20,
                    app_scope=WorkflowAutomationService.LOGISTICS_APP_SCOPE,
                )
                or sent_any
            )

        sent_ops = WorkflowAutomationService._notify_internal_ops(
            db,
            title="New Logistics Order",
            message=f"Order {order_id} was created for {destination_text}.",
            notification_type="logistics_order_created_ops",
            channels=("push", "email"),
            category="operational",
            dedupe_window_minutes=10,
            exclude_user_ids=[
                user_id for user_id in (customer_user_id, driver_user_id) if user_id is not None
            ],
            app_scope=WorkflowAutomationService.LOGISTICS_APP_SCOPE,
        )

        return sent_any or sent_ops

    @staticmethod
    def notify_logistics_order_rescheduled(
        db: Session,
        *,
        order_id: str,
        customer_user_id: int | None,
        scheduled_slot_start: datetime,
        scheduled_slot_end: datetime,
    ) -> bool:
        if customer_user_id is None:
            return False

        return WorkflowAutomationService._notify_channels(
            db,
            user_id=customer_user_id,
            title="Delivery Rescheduled",
            message=(
                f"Order {order_id} has been rescheduled to "
                f"{scheduled_slot_start:%Y-%m-%d %H:%M} - {scheduled_slot_end:%H:%M}. "
                "Please review the updated delivery window in the app."
            ),
            notification_type="logistics_order_rescheduled",
            channels=("push", "sms"),
            category="transactional",
            dedupe_window_minutes=20,
            app_scope=WorkflowAutomationService.LOGISTICS_APP_SCOPE,
        )

    @staticmethod
    def notify_logistics_transfer_update(
        db: Session,
        *,
        transfer_id: int,
        action: str,
        from_location_type: str,
        from_location_id: int,
        to_location_type: str,
        to_location_id: int,
        driver_user_id: int | None = None,
    ) -> bool:
        normalized_action = (action or "").strip().lower() or "updated"
        title_map = {
            "created": "Inventory Transfer Started",
            "received": "Inventory Transfer Received",
            "cancelled": "Inventory Transfer Cancelled",
        }
        title = title_map.get(normalized_action, "Inventory Transfer Updated")
        message = (
            f"Transfer #{transfer_id} was {normalized_action} from "
            f"{from_location_type} #{from_location_id} to {to_location_type} #{to_location_id}."
        )

        sent_ops = WorkflowAutomationService._notify_internal_ops(
            db,
            title=title,
            message=message,
            notification_type=f"logistics_transfer_{normalized_action}",
            channels=("push",),
            category="operational",
            dedupe_window_minutes=10,
            app_scope=WorkflowAutomationService.LOGISTICS_APP_SCOPE,
        )

        if driver_user_id is None:
            return sent_ops

        sent_driver = WorkflowAutomationService._notify_channels(
            db,
            user_id=driver_user_id,
            title=title,
            message=(
                f"{message} Open the driver app for next actions."
            ),
            notification_type=f"logistics_transfer_{normalized_action}_driver",
            channels=("push", "sms"),
            category="operational",
            bypass_preferences=True,
            dedupe_window_minutes=10,
            app_scope=WorkflowAutomationService.LOGISTICS_APP_SCOPE,
        )
        return sent_ops or sent_driver

    @staticmethod
    def notify_catalog_refund_requested(
        db: Session,
        *,
        user_id: int,
        order_id: int,
        amount: Decimal | float | int | str,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Refund Request Submitted",
            message=(
                f"Your refund request for order #{order_id} (INR {amount_text}) was submitted. "
                "We will update you once it is processed."
            ),
            notification_type="refund_requested",
            channels=("push", "email"),
            category="payment",
            dedupe_window_minutes=60,
        )

    @staticmethod
    def notify_pending_refund_reminder(
        db: Session,
        *,
        user_id: int,
        refund_id: int,
        amount: Decimal | float | int | str,
        hours_pending: int,
        escalate_ops: bool = False,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        sent_user = WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Refund Processing Update",
            message=(
                f"Refund #{refund_id} for INR {amount_text} is still being processed "
                f"({hours_pending} hour(s) pending)."
            ),
            notification_type="refund_pending_reminder",
            channels=("push", "email"),
            category="payment",
            dedupe_window_minutes=360,
        )
        if not escalate_ops:
            return sent_user
        sent_ops = WorkflowAutomationService._notify_internal_ops(
            db,
            title="Pending Refund Requires Review",
            message=(
                f"Refund #{refund_id} for user #{user_id} has been pending for {hours_pending} hour(s). "
                "Please review the reconciliation queue."
            ),
            notification_type="ops_refund_pending_review",
            dedupe_window_minutes=360,
            exclude_user_ids=[user_id],
        )
        return sent_user or sent_ops

    @staticmethod
    def notify_pending_withdrawal_reminder(
        db: Session,
        *,
        user_id: int,
        request_id: int,
        amount: Decimal | float | int | str,
        hours_pending: int,
        escalate_ops: bool = False,
    ) -> bool:
        amount_text = WorkflowAutomationService._money(amount)
        sent_user = WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Withdrawal Processing Update",
            message=(
                f"Withdrawal request #{request_id} for INR {amount_text} is still under review "
                f"({hours_pending} hour(s) pending)."
            ),
            notification_type="withdrawal_pending_reminder",
            channels=("push", "email"),
            category="payment",
            dedupe_window_minutes=240,
        )
        if not escalate_ops:
            return sent_user
        sent_ops = WorkflowAutomationService._notify_internal_ops(
            db,
            title="Pending Withdrawal Requires Review",
            message=(
                f"Withdrawal request #{request_id} for user #{user_id} has been pending for {hours_pending} hour(s). "
                "Please review payout processing."
            ),
            notification_type="ops_withdrawal_pending_review",
            dedupe_window_minutes=240,
            exclude_user_ids=[user_id],
        )
        return sent_user or sent_ops

    @staticmethod
    def notify_support_ticket_created(
        db: Session,
        *,
        user_id: int,
        ticket_id: int,
        subject: str,
        priority: str,
    ) -> bool:
        sent_user = WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Support Ticket Created",
            message=f"Ticket #{ticket_id} ({subject}) was created with {priority} priority.",
            notification_type="support_ticket_created",
            channels=("push", "email"),
            category="support",
            dedupe_window_minutes=60,
        )
        sent_ops = WorkflowAutomationService._notify_internal_ops(
            db,
            title="New Support Ticket",
            message=(
                f"New support ticket #{ticket_id} from user #{user_id}. "
                f"Subject: {subject}. Priority: {priority}."
            ),
            notification_type="ops_new_support_ticket",
            dedupe_window_minutes=30,
            exclude_user_ids=[user_id],
        )
        return sent_user or sent_ops

    @staticmethod
    def notify_support_user_reply(
        db: Session,
        *,
        user_id: int,
        ticket_id: int,
    ) -> bool:
        return WorkflowAutomationService._notify_internal_ops(
            db,
            title="Customer Replied to Support Ticket",
            message=f"User #{user_id} replied to support ticket #{ticket_id}.",
            notification_type="ops_support_customer_reply",
            dedupe_window_minutes=30,
            exclude_user_ids=[user_id],
        )

    @staticmethod
    def notify_support_agent_reply(
        db: Session,
        *,
        user_id: int,
        ticket_id: int,
    ) -> bool:
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Support Team Replied",
            message=f"Support has replied to ticket #{ticket_id}. Open the app to continue the conversation.",
            notification_type="support_agent_reply",
            channels=("push", "email", "sms"),
            category="support",
            dedupe_window_minutes=15,
        )

    @staticmethod
    def notify_support_ticket_sla_breach(
        db: Session,
        *,
        user_id: int,
        ticket_id: int,
        priority: str,
        hours_open: int,
    ) -> bool:
        sent_ops = WorkflowAutomationService._notify_internal_ops(
            db,
            title="Support SLA Breach",
            message=(
                f"Support ticket #{ticket_id} ({priority}) has been open for {hours_open} hour(s). "
                "Immediate attention required."
            ),
            notification_type="ops_support_sla_breach",
            dedupe_window_minutes=120,
            exclude_user_ids=[user_id],
        )
        sent_user = WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Support Ticket Update",
            message=(
                f"Ticket #{ticket_id} is still being worked on. "
                "Our team has been alerted to prioritize this request."
            ),
            notification_type="support_ticket_delay_notice",
            channels=("push",),
            category="support",
            dedupe_window_minutes=360,
        )
        return sent_ops or sent_user

    @staticmethod
    def notify_kyc_pending_reminder(
        db: Session,
        *,
        user_id: int,
        hours_pending: int,
    ) -> bool:
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="KYC Verification In Progress",
            message=(
                f"Your KYC verification is still under review ({hours_pending} hour(s) pending). "
                "We will notify you once it is completed."
            ),
            notification_type="kyc_pending_reminder",
            channels=("push", "email"),
            category="kyc",
            dedupe_window_minutes=720,
        )

    @staticmethod
    def notify_kyc_status_reviewed(
        db: Session,
        *,
        user_id: int,
        decision: str,
        reason: str | None = None,
    ) -> bool:
        decision_text = str(decision).strip().lower() or "updated"
        reason_text = f" Reason: {reason}" if reason else ""
        return WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="KYC Status Updated",
            message=f"Your KYC verification status is {decision_text}.{reason_text}",
            notification_type="kyc_status_reviewed",
            channels=("push", "email", "sms"),
            category="kyc",
            bypass_preferences=True,
            dedupe_window_minutes=30,
        )

    @staticmethod
    def notify_kyc_pending_escalation_ops(
        db: Session,
        *,
        user_id: int,
        hours_pending: int,
    ) -> bool:
        return WorkflowAutomationService._notify_internal_ops(
            db,
            title="KYC Review Escalation",
            message=(
                f"KYC for user #{user_id} has been pending for {hours_pending} hour(s). "
                "Please prioritize manual review."
            ),
            notification_type="ops_kyc_pending_escalation",
            dedupe_window_minutes=360,
            exclude_user_ids=[user_id],
        )

    @staticmethod
    def notify_geofence_violation(
        db: Session,
        *,
        user_id: int,
        rental_id: int,
        geofence_name: str,
        geofence_type: str,
    ) -> bool:
        sent_user = WorkflowAutomationService._notify_channels(
            db,
            user_id=user_id,
            title="Geofence Alert",
            message=(
                f"Rental #{rental_id} triggered a geofence alert in '{geofence_name}' ({geofence_type}). "
                "Please return to the allowed area."
            ),
            notification_type="geofence_violation",
            channels=("push", "sms"),
            category="security",
            dedupe_window_minutes=120,
        )
        sent_ops = WorkflowAutomationService._notify_internal_ops(
            db,
            title="Geofence Violation Detected",
            message=(
                f"Rental #{rental_id} (user #{user_id}) triggered geofence '{geofence_name}' "
                f"of type '{geofence_type}'."
            ),
            notification_type="ops_geofence_violation",
            category="security",
            dedupe_window_minutes=120,
            exclude_user_ids=[user_id],
        )
        return sent_user or sent_ops

    @staticmethod
    def notify_maintenance_schedule_overdue_ops(
        db: Session,
        *,
        entity_type: str,
        schedule_id: int,
        model_name: str | None,
        days_overdue: int,
    ) -> bool:
        model_part = f" model={model_name}," if model_name else ""
        return WorkflowAutomationService._notify_internal_ops(
            db,
            title="Maintenance Schedule Overdue",
            message=(
                f"Maintenance schedule #{schedule_id} ({entity_type}){model_part} "
                f"is overdue by {days_overdue} day(s)."
            ),
            notification_type="ops_maintenance_schedule_overdue",
            category="operational",
            dedupe_window_minutes=180,
        )
