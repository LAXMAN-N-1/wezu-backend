from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import logging
import math
import re
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Response
from sqlalchemy import func, inspect, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from app.api import deps
from app.core.config import settings
from app.db.session import get_session
from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.driver_profile import DriverProfile
from app.models.inventory import InventoryTransfer, InventoryTransferItem
from app.models.order import Order, OrderBattery
from app.models.financial import Transaction
from app.models.refund import Refund
from app.models.user import User
from app.models.warehouse import Rack, Shelf, Warehouse
from app.schemas.common import DataResponse, DataResponseWithPagination, PaginationMeta
from app.schemas.order import (
    OrderCreate,
    OrderRead,
    OrderSchedule,
    ProofOfDeliveryCreate,
    StatusUpdate,
)
from app.services.battery_consistency import (
    apply_battery_transition,
    assert_batteries_not_in_active_orders,
    assert_batteries_not_in_active_transfers,
    assert_battery_shelf_state_consistent,
    fetch_batteries_by_serials,
    get_single_active_warehouse_id,
    normalize_battery_serial,
    normalize_battery_serials,
)
from app.services.idempotency_service import (
    build_request_fingerprint,
    get_idempotent_replay,
    normalize_idempotency_key,
    record_idempotent_response,
)
from app.services.payment_service import PaymentService
from app.services.wallet_service import WalletService
from app.services.workflow_automation_service import WorkflowAutomationService
from app.services.order_realtime_outbox_service import OrderRealtimeOutboxService
from app.services.distributed_cache_service import DistributedCacheService

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_ORDER_STATUSES = {"pending", "in_transit", "delivered", "failed", "cancelled"}
VALID_ORDER_PRIORITIES = {"urgent", "normal", "low"}
VALID_ORDER_SORT_FIELDS = {"order_date", "updated_at", "estimated_delivery"}
VALID_SORT_DIRECTIONS = {"asc", "desc"}
VALID_TRANSITIONS = {
    "pending": {"in_transit", "cancelled"},
    "in_transit": {"delivered", "failed", "cancelled"},
    "failed": {"pending"},
    "delivered": set(),
    "cancelled": set(),
}
ACTIVE_DRIVER_ORDER_STATUSES = {"pending", "in_transit"}
ORDER_STATUS_EQUIVALENTS = {
    "pending": {"pending", "assigned", "new"},
    "in_transit": {
        "in_transit",
        "in-transit",
        "in transit",
        "in_progress",
        "in-progress",
        "in progress",
        "out_for_delivery",
        "out-for-delivery",
        "out for delivery",
        "intransit",
        "inprogress",
        "outfordelivery",
        "dispatched",
    },
    "delivered": {"delivered", "completed", "complete", "done"},
    "failed": {"failed", "failure", "delivery_failed", "delivery-failed"},
    "cancelled": {"cancelled", "canceled", "cancelled_order", "canceled_order"},
}
ACTIVE_DRIVER_ORDER_STATUSES_DB = set().union(
    *(ORDER_STATUS_EQUIVALENTS[status] for status in ACTIVE_DRIVER_ORDER_STATUSES)
)
TRANSFERABLE_BATTERY_STATUSES = {"available", "new", "ready"}
DRIVER_ASSIGNABLE_STATUSES = {"available", "onRoute"}
TERMINAL_STATUSES = {"delivered", "failed", "cancelled"}
INT32_MAX = 2_147_483_647
LOGISTICS_NOTIFICATION_APP_SCOPE = "logistics"
MIN_CUSTOMER_PHONE_DIGITS = 10
MAX_CUSTOMER_PHONE_DIGITS = 15
MAX_DESTINATION_LENGTH = 255
MAX_CUSTOMER_NAME_LENGTH = 120
MAX_ORDER_NOTES_LENGTH = 2000
MAX_TRACKING_NUMBER_LENGTH = 64
ORDER_LIST_CACHE_NAMESPACE = "wezu:orders:list:v1"


def _schema_to_dict(payload_obj: object) -> dict:
    if hasattr(payload_obj, "model_dump"):
        return payload_obj.model_dump(exclude_none=True)
    return payload_obj.dict(exclude_none=True)


def _order_list_cache_ttl_seconds() -> int:
    raw = int(getattr(settings, "ORDER_LIST_CACHE_TTL_SECONDS", 5) or 5)
    return max(1, min(30, raw))


def _order_list_cache_lock_ttl_seconds() -> int:
    raw = int(getattr(settings, "ORDER_LIST_CACHE_LOCK_TTL_SECONDS", 5) or 5)
    return max(1, min(30, raw))


def _order_list_count_cache_ttl_seconds() -> int:
    raw = int(getattr(settings, "ORDER_LIST_COUNT_CACHE_TTL_SECONDS", 8) or 8)
    return max(2, min(60, raw))


def _order_list_cache_ttl_jitter_seconds() -> int:
    raw = int(getattr(settings, "ORDER_LIST_CACHE_TTL_JITTER_SECONDS", 2) or 2)
    return max(0, min(15, raw))


def _order_list_cache_stale_ttl_seconds() -> int:
    raw = int(getattr(settings, "ORDER_LIST_CACHE_STALE_TTL_SECONDS", 30) or 30)
    return max(0, min(300, raw))


def _order_list_cache_lock_wait_ms() -> int:
    raw = int(getattr(settings, "ORDER_LIST_CACHE_LOCK_WAIT_MS", 500) or 500)
    return max(0, min(5000, raw))


def _order_list_cache_lock_poll_ms() -> int:
    raw = int(getattr(settings, "ORDER_LIST_CACHE_LOCK_POLL_MS", 30) or 30)
    return max(10, min(300, raw))


def _order_list_cache_key(payload: dict[str, Any]) -> str:
    return DistributedCacheService.build_key(ORDER_LIST_CACHE_NAMESPACE, payload)


def _order_list_count_cache_key(payload: dict[str, Any]) -> str:
    return DistributedCacheService.build_key(f"{ORDER_LIST_CACHE_NAMESPACE}:count", payload)


def _order_list_count_cache_get(cache_key: str) -> Optional[int]:
    payload = DistributedCacheService.get_json(cache_key)
    if isinstance(payload, int):
        return payload
    if isinstance(payload, str) and payload.isdigit():
        return int(payload)
    return None


def _order_list_count_cache_set(cache_key: str, value: int) -> None:
    DistributedCacheService.set_json(
        cache_key,
        int(value),
        ttl_seconds=_order_list_count_cache_ttl_seconds(),
        ttl_jitter_seconds=min(5, _order_list_cache_ttl_jitter_seconds()),
    )


def _canonical_order_status(raw_status: Optional[str]) -> str:
    status = str(raw_status or "").strip()
    if not status:
        return ""
    normalized = status.replace("-", "_").replace(" ", "_").lower()
    compact = normalized.replace("_", "")
    mapping = {
        "pending": "pending",
        "assigned": "pending",
        "new": "pending",
        "intransit": "in_transit",
        "inprogress": "in_transit",
        "outfordelivery": "in_transit",
        "dispatched": "in_transit",
        "delivered": "delivered",
        "completed": "delivered",
        "complete": "delivered",
        "done": "delivered",
        "failed": "failed",
        "failure": "failed",
        "deliveryfailed": "failed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "cancelledorder": "cancelled",
        "canceledorder": "cancelled",
    }
    return mapping.get(compact, normalized)


def _status_aliases_for(canonical_status: str) -> set[str]:
    aliases = set(ORDER_STATUS_EQUIVALENTS.get(canonical_status, {canonical_status}))
    aliases.add(canonical_status)
    return aliases


def _mark_order_assigned_if_pending(order: Order) -> bool:
    """
    Mark order status as assigned when a driver is attached and order was still in pending-like state.
    Returns True when status changed.
    """
    current = _canonical_order_status(order.status)
    if current == "pending" and str(order.status).strip().lower() != "assigned":
        order.status = "assigned"
        order.updated_at = datetime.utcnow()
        return True
    return False


def _emit_order_realtime_update(
    *,
    session: Session,
    event_type: str,
    order: Order,
    actor_user_id: Optional[int],
    metadata: Optional[dict] = None,
    request_idempotency_key: Optional[str] = None,
) -> None:
    """Queue durable order update event for realtime websocket fanout."""
    try:
        payload = {
            "event_type": event_type,
            "order_id": order.id,
            "status": order.status,
            "canonical_status": _canonical_order_status(order.status) or order.status,
            "assigned_driver_id": order.assigned_driver_id,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "actor_user_id": actor_user_id,
            "order": OrderRead.model_validate(order).model_dump(mode="json"),
        }
        if metadata:
            payload["metadata"] = metadata
        OrderRealtimeOutboxService.enqueue(
            session,
            order_id=order.id,
            event_type=event_type,
            payload=payload,
            idempotency_key=request_idempotency_key,
        )
    except Exception:
        logger.exception(
            "Order realtime enqueue failed event_type=%s order_id=%s actor_user_id=%s",
            event_type,
            getattr(order, "id", None),
            actor_user_id,
        )


def _parse_driver_id(raw_driver_id: str) -> int:
    clean_id = str(raw_driver_id).strip()
    if clean_id.upper().startswith("D-"):
        clean_id = clean_id[2:].strip()
    if not clean_id.isdigit():
        raise HTTPException(status_code=400, detail="Invalid driver ID format")
    parsed_id = int(clean_id)
    if parsed_id < 1 or parsed_id > INT32_MAX:
        raise HTTPException(
            status_code=400,
            detail="Driver ID is out of supported range for numeric primary keys",
        )
    return parsed_id


def _normalize_driver_lookup_token(raw_driver_id: Any) -> str:
    if isinstance(raw_driver_id, bool):
        raise HTTPException(status_code=422, detail="driver_id must be a string or number")
    driver_token = str(raw_driver_id).strip()
    if not driver_token:
        raise HTTPException(status_code=422, detail="driver_id must not be empty")
    return driver_token


def _parse_int32_id_candidate(raw_driver_id: str) -> Optional[int]:
    clean_id = str(raw_driver_id).strip()
    if clean_id.upper().startswith("D-"):
        clean_id = clean_id[2:].strip()
    if not clean_id.isdigit():
        return None
    parsed_id = int(clean_id)
    if parsed_id < 1 or parsed_id > INT32_MAX:
        return None
    return parsed_id


def _extract_driver_reference(
    driver_id_query: Optional[str],
    body: Optional[dict],
    query_aliases: Optional[List[Optional[str]]] = None,
) -> str:
    candidate_values: list[str] = []

    for candidate in [driver_id_query, *(query_aliases or [])]:
        if candidate is not None:
            candidate_values.append(_normalize_driver_lookup_token(candidate))

    if body is not None:
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="Request body must be a JSON object")
        for field_name in (
            "driver_id",
            "assigned_driver_id",
            "driverId",
            "assignedDriverId",
        ):
            if field_name in body and body.get(field_name) is not None:
                candidate_values.append(_normalize_driver_lookup_token(body.get(field_name)))

        nested_driver = body.get("driver")
        if isinstance(nested_driver, dict):
            for nested_key in ("id", "driver_id", "driverId"):
                if nested_driver.get(nested_key) is not None:
                    candidate_values.append(
                        _normalize_driver_lookup_token(nested_driver.get(nested_key))
                    )

    if not candidate_values:
        raise HTTPException(
            status_code=422,
            detail="driver_id is required in query or JSON body (driver_id / assigned_driver_id)",
        )

    unique_values = {value for value in candidate_values}
    if len(unique_values) > 1:
        raise HTTPException(
            status_code=422,
            detail="Conflicting driver_id values provided in query/body",
        )
    return candidate_values[0]


def _table_has_column(session: Session, table_name: str, column_name: str) -> bool:
    bind = session.get_bind()
    if bind is None:
        return False
    try:
        inspector = inspect(bind)
        return any(column.get("name") == column_name for column in inspector.get_columns(table_name))
    except Exception:
        return False


def _first_column_value(row: Any) -> Any:
    if row is None:
        return None
    try:
        return row[0]
    except Exception:
        return row


def _resolve_order_by_optional_column(session: Session, column_name: str, lookup_value: str) -> Optional[Order]:
    if not _table_has_column(session, Order.__tablename__, column_name):
        return None
    row = session.execute(
        text(f"SELECT id FROM {Order.__tablename__} WHERE {column_name} = :lookup LIMIT 1"),
        {"lookup": lookup_value},
    ).first()
    if row is None:
        return None
    order_id = _first_column_value(row)
    if order_id is None:
        return None
    return session.get(Order, str(order_id))


def _resolve_driver_by_optional_column(session: Session, column_name: str, lookup_value: str) -> Optional[DriverProfile]:
    if not _table_has_column(session, DriverProfile.__tablename__, column_name):
        return None
    row = session.execute(
        text(f"SELECT id FROM {DriverProfile.__tablename__} WHERE {column_name} = :lookup LIMIT 1"),
        {"lookup": lookup_value},
    ).first()
    if row is None:
        return None
    driver_id = _first_column_value(row)
    parsed_driver_id = _parse_int32_id_candidate(driver_id)
    if parsed_driver_id is None:
        return None
    return session.get(DriverProfile, parsed_driver_id)


def _resolve_order_for_assignment(session: Session, order_reference: str) -> Optional[Order]:
    reference = str(order_reference).strip()
    if not reference:
        return None

    order = session.get(Order, reference)
    if order:
        return order

    order = session.exec(select(Order).where(Order.tracking_number == reference).limit(1)).first()
    if order:
        return order

    for legacy_column in ("order_number", "external_order_code", "order_code"):
        order = _resolve_order_by_optional_column(session, legacy_column, reference)
        if order:
            return order

    return None


def _resolve_order_or_404(session: Session, order_reference: str, *, detail: str = "Order not found") -> Order:
    order = _resolve_order_for_assignment(session, order_reference)
    if not order:
        raise HTTPException(status_code=404, detail=detail)
    return order


def _resolve_driver_for_assignment(session: Session, driver_reference: str) -> Optional[DriverProfile]:
    reference = _normalize_driver_lookup_token(driver_reference)
    int_id_candidate = _parse_int32_id_candidate(reference)

    if int_id_candidate is not None:
        driver = session.get(DriverProfile, int_id_candidate)
        if driver:
            return driver

    for phone_candidate in _phone_candidates(reference):
        driver = session.exec(
            select(DriverProfile).where(DriverProfile.phone_number == phone_candidate).limit(1)
        ).first()
        if driver:
            return driver

        user_id = session.exec(
            select(User.id).where(User.phone_number == phone_candidate).limit(1)
        ).first()
        user_id_value = _first_column_value(user_id)
        parsed_user_id = _parse_int32_id_candidate(str(user_id_value)) if user_id_value is not None else None
        if parsed_user_id is not None:
            driver = session.exec(
                select(DriverProfile).where(DriverProfile.user_id == parsed_user_id).limit(1)
            ).first()
            if driver:
                return driver

    if int_id_candidate is not None:
        driver = session.exec(
            select(DriverProfile).where(DriverProfile.user_id == int_id_candidate).limit(1)
        ).first()
        if driver:
            return driver

    for legacy_column in ("driver_code", "external_driver_code", "external_driver_id"):
        driver = _resolve_driver_by_optional_column(session, legacy_column, reference)
        if driver:
            return driver

    return None


def _user_role_names(current_user: User) -> List[str]:
    roles = getattr(current_user, "roles", None) or []
    role_names = {str(role.name) for role in roles if getattr(role, "name", None)}
    if getattr(current_user, "is_superuser", False):
        role_names.add("superuser")
    return sorted(role_names)


def _canonical_driver_status(raw_status: Optional[str]) -> str:
    status = str(raw_status or "").strip()
    if not status:
        return ""
    collapsed = status.replace("-", "_").replace(" ", "_")
    compact_key = collapsed.replace("_", "").lower()
    status_map = {
        "available": "available",
        "onroute": "onRoute",
        "busy": "busy",
        "offline": "offline",
        "breaktime": "break_time",
    }
    return status_map.get(compact_key, status)


def _phone_candidates(raw_phone: Optional[str]) -> List[str]:
    if not raw_phone:
        return []
    stripped = str(raw_phone).strip()
    digits = "".join(ch for ch in stripped if ch.isdigit())
    candidates = {stripped, digits}
    if digits:
        candidates.add(f"+{digits}")
        if len(digits) >= 10:
            last_ten = digits[-10:]
            candidates.add(last_ten)
            candidates.add(f"+91{last_ten}")
    return [candidate for candidate in candidates if candidate]


def _normalize_customer_phone(raw_phone: Optional[str]) -> Optional[str]:
    if raw_phone is None:
        return None
    cleaned = "".join(ch for ch in str(raw_phone).strip() if ch.isdigit())
    if not cleaned:
        raise HTTPException(status_code=400, detail="customer_phone must contain digits")
    if len(cleaned) < MIN_CUSTOMER_PHONE_DIGITS or len(cleaned) > MAX_CUSTOMER_PHONE_DIGITS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"customer_phone must have between {MIN_CUSTOMER_PHONE_DIGITS} and "
                f"{MAX_CUSTOMER_PHONE_DIGITS} digits"
            ),
        )
    return cleaned


def _normalize_destination(raw_destination: Optional[object]) -> str:
    destination = str(raw_destination or "").strip()
    if not destination:
        raise HTTPException(status_code=400, detail="destination is required")
    if len(destination) > MAX_DESTINATION_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"destination must be {MAX_DESTINATION_LENGTH} characters or fewer",
        )
    return destination


def _normalize_customer_name(raw_customer_name: Optional[object]) -> str:
    customer_name = str(raw_customer_name or "Walk-in Customer").strip()
    if not customer_name:
        raise HTTPException(status_code=400, detail="customer_name is required")
    if len(customer_name) > MAX_CUSTOMER_NAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"customer_name must be {MAX_CUSTOMER_NAME_LENGTH} characters or fewer",
        )
    return customer_name


def _normalize_order_notes(raw_notes: Optional[object]) -> Optional[str]:
    if raw_notes is None:
        return None
    notes = str(raw_notes).strip()
    if not notes:
        return None
    if len(notes) > MAX_ORDER_NOTES_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"notes must be {MAX_ORDER_NOTES_LENGTH} characters or fewer",
        )
    return notes


def _normalize_pod_media_url(
    raw_url: Optional[object],
    *,
    field_name: str,
    required: bool = False,
) -> Optional[str]:
    value = (str(raw_url).strip() if raw_url is not None else "")
    if not value:
        if required:
            raise HTTPException(status_code=400, detail=f"{field_name} is required for proof of delivery")
        return None

    lowered = value.lower()
    if lowered.startswith(("file://", "content://", "blob:", "data:")):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{field_name} must be a backend-hosted or HTTPS URL. "
                "Local/device URIs are not allowed."
            ),
        )

    if value.startswith("uploads/"):
        return f"/{value}"
    if value.startswith("/"):
        return value
    if lowered.startswith(("http://", "https://")):
        return value

    raise HTTPException(
        status_code=400,
        detail=(
            f"{field_name} must be an absolute path (e.g., /uploads/...) "
            "or a full HTTPS URL."
        ),
    )


def _normalize_tracking_number(raw_tracking_number: Optional[object], *, order_id: str) -> str:
    tracking_number = str(raw_tracking_number or "").strip().upper()
    if tracking_number:
        if len(tracking_number) > MAX_TRACKING_NUMBER_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"tracking_number must be {MAX_TRACKING_NUMBER_LENGTH} characters or fewer",
            )
        return tracking_number
    return f"TRK-{order_id}"


def _normalize_order_datetime(raw_value: Optional[datetime], *, field_name: str) -> Optional[datetime]:
    if raw_value is None:
        return None
    if not isinstance(raw_value, datetime):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a valid datetime")
    if raw_value.tzinfo is not None:
        return raw_value.astimezone(timezone.utc).replace(tzinfo=None)
    return raw_value


def _normalize_order_priority(raw_priority: Optional[object]) -> str:
    priority = str(raw_priority or "normal").strip().lower()
    if priority not in VALID_ORDER_PRIORITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority '{raw_priority}'. Allowed: {sorted(VALID_ORDER_PRIORITIES)}",
        )
    return priority


def _normalize_total_value(raw_total_value: Optional[object]) -> Decimal:
    try:
        normalized = Decimal(str(raw_total_value if raw_total_value is not None else 0))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="total_value must be a valid decimal amount") from exc
    if normalized < Decimal("0"):
        raise HTTPException(status_code=400, detail="total_value cannot be negative")
    return normalized


def _normalize_order_coordinates(
    raw_latitude: Optional[object],
    raw_longitude: Optional[object],
) -> tuple[Optional[float], Optional[float]]:
    def _coerce(value: Optional[object], *, field_name: str) -> Optional[float]:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"{field_name} must be a valid number") from exc
        if not math.isfinite(numeric):
            raise HTTPException(status_code=400, detail=f"{field_name} must be a finite number")
        return numeric

    latitude = _coerce(raw_latitude, field_name="latitude")
    longitude = _coerce(raw_longitude, field_name="longitude")
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=400,
            detail="latitude and longitude must be provided together",
        )
    if latitude is not None and not (-90 <= latitude <= 90):
        raise HTTPException(status_code=400, detail="latitude must be between -90 and 90")
    if longitude is not None and not (-180 <= longitude <= 180):
        raise HTTPException(status_code=400, detail="longitude must be between -180 and 180")
    return latitude, longitude


def _acquire_tracking_number_lock(session: Session, tracking_number: str) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"logistics_orders_tracking:{tracking_number}"},
    )


def _raise_create_order_integrity_error(exc: IntegrityError) -> None:
    lowered = str(getattr(exc, "orig", exc)).lower()
    if "logistics_orders_pkey" in lowered or "duplicate key" in lowered and "logistics_orders" in lowered:
        raise HTTPException(status_code=409, detail="Order ID already exists")
    if "tracking" in lowered and "unique" in lowered:
        raise HTTPException(status_code=409, detail="tracking_number is already in use")
    if "assigned_driver_id" in lowered and "foreign key" in lowered:
        raise HTTPException(status_code=409, detail="Assigned driver not found")
    if "uq_logistics_order_battery" in lowered:
        raise HTTPException(status_code=409, detail="Duplicate battery assignment for this order")
    raise HTTPException(status_code=500, detail="Failed to create order")


def _resolve_customer_user(session: Session, order: Order) -> Optional[User]:
    for candidate in _phone_candidates(order.customer_phone):
        user = session.exec(select(User).where(User.phone_number == candidate)).first()
        if user:
            return user
    return None


def _send_order_sms_with_tracking(
    session: Session,
    order: Order,
    *,
    title: str,
    message: str,
    notification_type: str,
    category: str = "transactional",
    defer_delivery: bool = False,
    app_scope: Optional[str] = LOGISTICS_NOTIFICATION_APP_SCOPE,
) -> bool:
    from app.services.notification_service import NotificationService
    from app.services.sms_service import SMSService

    target_user = _resolve_customer_user(session, order)
    if target_user:
        notification = NotificationService.send_notification(
            db=session,
            user=target_user,
            title=title,
            message=message,
            type=notification_type,
            channel="sms",
            category=category,
            bypass_preferences=True,
            defer_delivery=defer_delivery,
            app_scope=app_scope,
        )
        if notification.status in {"sent", "queued"}:
            return True

    return bool(SMSService.send_sms(order.customer_phone or "", message))


def _build_tracking_link(order: Order) -> str:
    base = settings.TRACKING_BASE_URL.rstrip("/")
    tracking_ref = order.tracking_number or str(order.id)
    return f"{base}/{tracking_ref}"


def _auto_notify_order_status_update(session: Session, order: Order, new_status: str) -> None:
    if not order.customer_phone:
        return

    status_key = (new_status or "").strip().lower()
    if status_key == "in_transit":
        title = "Order Out for Delivery"
        message = f"Your order {order.id} is out for delivery. Track it here: {_build_tracking_link(order)}"
    elif status_key == "delivered":
        title = "Order Delivered"
        message = f"Your order {order.id} was delivered successfully."
    elif status_key == "failed":
        title = "Order Delivery Failed"
        reason = f" Reason: {order.failure_reason}" if order.failure_reason else ""
        message = f"We could not deliver order {order.id}.{reason}"
    elif status_key == "cancelled":
        title = "Order Cancelled"
        message = f"Order {order.id} has been cancelled."
    else:
        return

    try:
        _send_order_sms_with_tracking(
            session,
            order,
            title=title,
            message=message,
            notification_type=f"order_{status_key}",
            category="transactional",
            defer_delivery=True,
        )
    except Exception:
        logger.exception("Automatic order status notification failed for order_id=%s status=%s", order.id, new_status)


def _auto_notify_driver_assignment(
    session: Session,
    *,
    order: Order,
    driver: DriverProfile,
) -> None:
    driver_display_name = (driver.name or "").strip() or (driver.phone_number or "").strip() or f"Driver #{driver.id}"
    customer_user = _resolve_customer_user(session, order)
    customer_user_id = int(customer_user.id) if customer_user and customer_user.id is not None else None
    driver_user_id = int(driver.user_id) if driver.user_id is not None else None

    try:
        sent = WorkflowAutomationService.notify_logistics_order_driver_assigned(
            session,
            order_id=order.id,
            customer_user_id=customer_user_id,
            driver_user_id=driver_user_id,
            driver_display_name=driver_display_name,
            scheduled_slot_start=order.scheduled_slot_start,
            scheduled_slot_end=order.scheduled_slot_end,
        )
        if not sent and order.customer_phone:
            _send_order_sms_with_tracking(
                session,
                order,
                title="Driver Assigned",
                message=(
                    f"{driver_display_name} has been assigned to order {order.id}. "
                    f"Track it here: {_build_tracking_link(order)}"
                ),
                notification_type="order_driver_assigned",
                category="transactional",
                defer_delivery=True,
            )
    except Exception:
        logger.exception("Automatic driver-assignment notification failed for order_id=%s", order.id)


def _auto_notify_order_rescheduled(session: Session, order: Order) -> None:
    if order.scheduled_slot_start is None or order.scheduled_slot_end is None:
        return
    customer_user = _resolve_customer_user(session, order)
    customer_user_id = int(customer_user.id) if customer_user and customer_user.id is not None else None

    try:
        sent = WorkflowAutomationService.notify_logistics_order_rescheduled(
            session,
            order_id=order.id,
            customer_user_id=customer_user_id,
            scheduled_slot_start=order.scheduled_slot_start,
            scheduled_slot_end=order.scheduled_slot_end,
        )
        if not sent and order.customer_phone:
            _send_order_sms_with_tracking(
                session,
                order,
                title="Delivery Rescheduled",
                message=(
                    f"Order {order.id} has been rescheduled to "
                    f"{order.scheduled_slot_start:%Y-%m-%d %H:%M} - {order.scheduled_slot_end:%H:%M}."
                ),
                notification_type="order_rescheduled",
                category="transactional",
                defer_delivery=True,
            )
    except Exception:
        logger.exception("Automatic reschedule notification failed for order_id=%s", order.id)


def _auto_notify_order_created(
    session: Session,
    *,
    order: Order,
    assigned_driver: Optional[DriverProfile] = None,
) -> None:
    customer_user = _resolve_customer_user(session, order)
    customer_user_id = int(customer_user.id) if customer_user and customer_user.id is not None else None
    assigned_driver_user_id = (
        int(assigned_driver.user_id)
        if assigned_driver and assigned_driver.user_id is not None
        else None
    )

    try:
        sent = WorkflowAutomationService.notify_logistics_order_created(
            session,
            order_id=order.id,
            destination=order.destination,
            customer_user_id=customer_user_id,
            driver_user_id=assigned_driver_user_id,
            scheduled_slot_start=order.scheduled_slot_start,
            scheduled_slot_end=order.scheduled_slot_end,
        )
        if not sent and order.customer_phone:
            _send_order_sms_with_tracking(
                session,
                order,
                title="Order Created",
                message=(
                    f"Order {order.id} was created successfully. "
                    f"Track it here: {_build_tracking_link(order)}"
                ),
                notification_type="logistics_order_created",
                category="transactional",
                defer_delivery=True,
            )
    except Exception:
        logger.exception("Automatic order-created notification failed for order_id=%s", order.id)


def _parse_assigned_battery_ids(raw_ids: Optional[object]) -> List[str]:
    if raw_ids is None:
        return []

    if not isinstance(raw_ids, list):
        raise HTTPException(status_code=400, detail="assigned_battery_ids must be a JSON array")
    if not raw_ids:
        return []
    return normalize_battery_serials(raw_ids, field_name="assigned_battery_ids")


def _fetch_batteries_by_serials(
    session: Session,
    battery_ids: List[str],
    *,
    for_update: bool = False,
) -> List[Battery]:
    return fetch_batteries_by_serials(
        session,
        battery_ids,
        field_name="assigned_battery_ids",
        require_non_empty=False,
        for_update=for_update,
    )


def _log_battery_event(
    session: Session,
    battery_id: int,
    event_type: str,
    description: str,
    actor_id: Optional[int] = None,
) -> None:
    session.add(
        BatteryLifecycleEvent(
            battery_id=battery_id,
            event_type=event_type,
            description=description,
            actor_id=actor_id,
        )
    )


def _set_driver_status(session: Session, driver_id: int, status: str) -> None:
    driver = session.get(DriverProfile, driver_id)
    if not driver:
        return

    driver.status = status
    driver.is_online = status in {"available", "onRoute"}
    driver.last_location_update = datetime.utcnow()
    session.add(driver)


def _release_driver_if_idle(session: Session, order: Order) -> None:
    if not order.assigned_driver_id:
        return

    active_order = session.exec(
        select(Order.id)
        .where(
            Order.assigned_driver_id == order.assigned_driver_id,
            Order.id != order.id,
            Order.status.in_(ACTIVE_DRIVER_ORDER_STATUSES_DB),
        )
        .limit(1)
    ).first()

    if not active_order:
        _set_driver_status(session, order.assigned_driver_id, "available")


def _persist_order_batteries(session: Session, order_id: str, battery_ids: List[str]) -> None:
    if not battery_ids:
        return

    canonical_ids = [normalize_battery_serial(battery_id) for battery_id in battery_ids]
    batteries = _fetch_batteries_by_serials(session, canonical_ids, for_update=False)
    battery_pk_by_serial = {
        normalize_battery_serial(battery.serial_number): battery.id
        for battery in batteries
        if battery.id is not None
    }

    existing_ids = {
        normalize_battery_serial(serial)
        for serial in session.exec(
            select(OrderBattery.battery_id).where(OrderBattery.order_id == order_id)
        ).all()
    }
    for normalized in canonical_ids:
        if normalized in existing_ids:
            continue
        session.add(
            OrderBattery(
                order_id=order_id,
                battery_id=normalized,
                battery_pk=battery_pk_by_serial.get(normalized),
            )
        )


def _persist_missing_order_batteries(
    session: Session,
    *,
    order_id: str,
    battery_ids: List[str],
) -> None:
    if not battery_ids:
        return

    savepoint = session.begin_nested()
    try:
        _persist_order_batteries(session, order_id, battery_ids)
        session.flush()
        savepoint.commit()
    except IntegrityError:
        # Another concurrent request may have inserted the same rows.
        savepoint.rollback()


def _parse_order_assigned_battery_ids_json(order: Order) -> List[str]:
    raw_assigned = (order.assigned_battery_ids or "").strip()
    if not raw_assigned:
        return []

    try:
        parsed = json.loads(raw_assigned)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Order '{order.id}' has invalid assigned_battery_ids JSON",
        ) from exc

    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=409,
            detail=f"Order '{order.id}' assigned_battery_ids must be a JSON array",
        )

    normalized_raw: List[str] = []
    for idx, value in enumerate(parsed):
        if not isinstance(value, str):
            raise HTTPException(
                status_code=409,
                detail=f"Order '{order.id}' assigned_battery_ids[{idx}] must be a string battery serial",
            )
        normalized_raw.append(value)

    return normalize_battery_serials(
        normalized_raw,
        field_name="assigned_battery_ids",
        require_non_empty=False,
    )


def _get_order_battery_ids(session: Session, order: Order) -> List[str]:
    indexed_rows = session.exec(
        select(OrderBattery.battery_id)
        .where(OrderBattery.order_id == order.id)
        .order_by(OrderBattery.id.asc())
    ).all()
    indexed_batteries = normalize_battery_serials(
        list(indexed_rows),
        field_name="assigned_battery_ids",
        require_non_empty=False,
    )
    legacy_batteries = _parse_order_assigned_battery_ids_json(order)

    if not indexed_batteries and not legacy_batteries:
        if _canonical_order_status(order.status) in {"in_transit", "delivered"}:
            raise HTTPException(
                status_code=409,
                detail=f"Order '{order.id}' has no indexed battery assignments",
            )
        return []

    if not indexed_batteries:
        _persist_missing_order_batteries(
            session,
            order_id=order.id,
            battery_ids=legacy_batteries,
        )
        return legacy_batteries

    if not legacy_batteries:
        return indexed_batteries

    indexed_set = set(indexed_batteries)
    missing_indexed = [serial for serial in legacy_batteries if serial not in indexed_set]
    if missing_indexed:
        _persist_missing_order_batteries(
            session,
            order_id=order.id,
            battery_ids=missing_indexed,
        )
        return indexed_batteries + missing_indexed

    return indexed_batteries


def _assert_batteries_not_in_other_active_orders(
    session: Session,
    battery_ids: List[str],
    *,
    exclude_order_id: Optional[str] = None,
) -> None:
    assert_batteries_not_in_active_orders(
        session,
        battery_ids,
        exclude_order_id=exclude_order_id,
    )


def _assert_driver_available_for_order(
    session: Session,
    driver_id: int,
    *,
    exclude_order_id: Optional[str] = None,
    allow_busy: bool = False,
    check_active_conflict: bool = True,
    for_update: bool = False,
) -> None:
    if for_update:
        driver = session.exec(
            select(DriverProfile).where(DriverProfile.id == driver_id).with_for_update()
        ).first()
    else:
        driver = session.get(DriverProfile, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Assigned driver not found")

    driver_status = _canonical_driver_status(driver.status)
    if driver_status and driver_status != driver.status:
        driver.status = driver_status
        session.add(driver)

    valid_statuses = set(DRIVER_ASSIGNABLE_STATUSES)
    if allow_busy:
        valid_statuses.add("busy")

    if driver_status not in valid_statuses:
        raise HTTPException(
            status_code=409,
            detail=f"Driver is '{driver_status or driver.status}'. Allowed statuses: {sorted(valid_statuses)}",
        )

    if check_active_conflict:
        conflict_query = (
            select(Order.id, Order.status)
            .where(
                Order.assigned_driver_id == driver_id,
                Order.status.in_(ACTIVE_DRIVER_ORDER_STATUSES_DB),
            )
            .limit(1)
        )
        if exclude_order_id:
            conflict_query = conflict_query.where(Order.id != exclude_order_id)

        conflicting_order = session.exec(conflict_query).first()
        if conflicting_order:
            conflicting_order_id = conflicting_order[0]
            conflicting_order_status = conflicting_order[1]
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Driver already assigned to active order '{conflicting_order_id}' "
                    f"(status '{conflicting_order_status}')"
                ),
            )


def _reserve_order_batteries(
    session: Session,
    order: Order,
    *,
    battery_ids: Optional[List[str]] = None,
    exclude_order_id: Optional[str] = None,
) -> None:
    order_battery_ids = battery_ids if battery_ids is not None else _get_order_battery_ids(session, order)
    batteries = _fetch_batteries_by_serials(session, order_battery_ids, for_update=True)
    _assert_batteries_not_in_other_active_orders(
        session,
        order_battery_ids,
        exclude_order_id=exclude_order_id,
    )
    assert_batteries_not_in_active_transfers(session, order_battery_ids)

    for battery in batteries:
        serial = normalize_battery_serial(battery.serial_number)
        battery.serial_number = serial
        if battery.status not in TRANSFERABLE_BATTERY_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Battery {serial} is '{battery.status}', cannot assign",
            )

        if battery.location_type not in {"warehouse", "station", "shelf"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Battery {serial} is at '{battery.location_type}' and cannot be reserved. "
                    "Move battery to warehouse/station inventory first."
                ),
            )
        if battery.location_id is None:
            raise HTTPException(
                status_code=409,
                detail=f"Battery {serial} has location_type '{battery.location_type}' but missing location_id",
            )
        if battery.location_type == "shelf":
            assert_battery_shelf_state_consistent(session, battery)

        apply_battery_transition(
            session,
            battery=battery,
            to_status="reserved",
            to_location_type=battery.location_type,
            to_location_id=battery.location_id,
            event_type="reserved",
            event_description=f"Reserved for order {order.id}",
            exclude_order_id=exclude_order_id,
        )


_DISPATCH_SOURCE_PATTERN = re.compile(
    r"from\s+(?P<location_type>warehouse|station|shelf|customer)(?:\s+#(?P<location_id>\d+))?",
    re.IGNORECASE,
)
_DISPATCH_SOURCE_MACHINE_PATTERN = re.compile(
    r"(?:^|[;|\s])source=(?P<location_type>warehouse|station|shelf|customer)"
    r"(?::(?P<location_id>\d+))?(?:[;|\s]|$)",
    re.IGNORECASE,
)


def _build_dispatch_event_description(
    order_id: str,
    source_location_type: str,
    source_location_id: Optional[int],
) -> str:
    source_token = (
        f"{source_location_type}:{source_location_id}"
        if source_location_id is not None
        else source_location_type
    )
    source_label = (
        f"{source_location_type} #{source_location_id}"
        if source_location_id is not None
        else source_location_type
    )
    return (
        f"event=dispatched;order={order_id};source={source_token};"
        f" note=Dispatched with order {order_id} from {source_label}"
    )


def _find_dispatch_event_description_for_order(
    session: Session,
    *,
    battery_id: int,
    order_id: str,
) -> Optional[str]:
    descriptions = session.exec(
        select(BatteryLifecycleEvent.description)
        .where(
            BatteryLifecycleEvent.battery_id == battery_id,
            BatteryLifecycleEvent.event_type == "dispatched",
        )
        .order_by(BatteryLifecycleEvent.timestamp.desc(), BatteryLifecycleEvent.id.desc())
    ).all()
    legacy_token = f"order {order_id}".lower()
    machine_token = f"order={order_id}".lower()
    for description in descriptions:
        value = (description or "").lower()
        if machine_token in value or legacy_token in value:
            return description
    return None


def _extract_dispatch_source_from_event(description: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    if not description:
        return None, None
    machine_match = _DISPATCH_SOURCE_MACHINE_PATTERN.search(description)
    if machine_match:
        location_type = machine_match.group("location_type").lower()
        location_id_raw = machine_match.group("location_id")
        return location_type, int(location_id_raw) if location_id_raw else None
    match = _DISPATCH_SOURCE_PATTERN.search(description)
    if not match:
        return None, None
    location_type = match.group("location_type").lower()
    location_id_raw = match.group("location_id")
    return location_type, int(location_id_raw) if location_id_raw else None


def _resolve_release_location_for_order(session: Session, battery: Battery, order: Order) -> tuple[str, Optional[int]]:
    dispatch_event_description = _find_dispatch_event_description_for_order(
        session,
        battery_id=battery.id,
        order_id=order.id,
    )
    dispatch_location_type, dispatch_location_id = _extract_dispatch_source_from_event(dispatch_event_description)
    if dispatch_location_type in {"warehouse", "station", "shelf"} and dispatch_location_id is not None:
        return dispatch_location_type, dispatch_location_id
    if dispatch_location_type == "customer":
        return "customer", None

    if battery.location_type in {"warehouse", "station", "shelf"} and battery.location_id is not None:
        return battery.location_type, battery.location_id
    if battery.location_type == "customer":
        return "customer", None

    fallback_warehouse_id = get_single_active_warehouse_id(session)
    if fallback_warehouse_id is not None:
        return "warehouse", fallback_warehouse_id

    raise HTTPException(
        status_code=409,
        detail=(
            f"Cannot resolve release location for battery {battery.serial_number} on order {order.id}. "
            "Dispatch source location is unknown in a multi-warehouse context."
        ),
    )


def _resolve_warehouse_id_from_shelf(session: Session, shelf_id: Optional[int]) -> Optional[int]:
    if shelf_id is None:
        return None

    shelf = session.get(Shelf, shelf_id)
    if not shelf:
        return None
    rack = session.get(Rack, shelf.rack_id)
    if not rack:
        return None
    return rack.warehouse_id


def _resolve_warehouse_id_from_station_history(
    session: Session,
    *,
    battery_serial: str,
    station_id: Optional[int],
) -> Optional[int]:
    if station_id is None:
        return None

    bind = session.get_bind()
    if bind is None:
        return None
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if "inventory_transfers" not in table_names or "inventory_transfer_items" not in table_names:
        return None

    normalized_serial = normalize_battery_serial(battery_serial)
    source_row = session.exec(
        select(
            InventoryTransfer.from_location_type,
            InventoryTransfer.from_location_id,
        )
        .join(InventoryTransferItem, InventoryTransferItem.transfer_id == InventoryTransfer.id)
        .where(
            InventoryTransfer.status == "completed",
            InventoryTransfer.to_location_type == "station",
            InventoryTransfer.to_location_id == station_id,
            func.upper(InventoryTransferItem.battery_id) == normalized_serial,
        )
        .order_by(
            InventoryTransfer.completed_at.desc(),
            InventoryTransfer.updated_at.desc(),
            InventoryTransfer.id.desc(),
        )
        .limit(1)
    ).first()
    if source_row:
        from_location_type, from_location_id = source_row
        from_location_type = (from_location_type or "").strip().lower()
        if from_location_type == "warehouse" and from_location_id is not None:
            return from_location_id
        if from_location_type == "shelf":
            return _resolve_warehouse_id_from_shelf(session, from_location_id)

    legacy_candidates = session.exec(
        select(
            InventoryTransfer.from_location_type,
            InventoryTransfer.from_location_id,
            InventoryTransfer.items,
        )
        .where(
            InventoryTransfer.status == "completed",
            InventoryTransfer.to_location_type == "station",
            InventoryTransfer.to_location_id == station_id,
        )
        .order_by(
            InventoryTransfer.completed_at.desc(),
            InventoryTransfer.updated_at.desc(),
            InventoryTransfer.id.desc(),
        )
        .limit(50)
    ).all()
    for candidate_from_type, candidate_from_id, candidate_items in legacy_candidates:
        raw_items = (candidate_items or "").strip()
        if not raw_items:
            continue
        try:
            parsed_items = json.loads(raw_items)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(parsed_items, list):
            continue

        normalized_items = set()
        for raw_serial in parsed_items:
            if not isinstance(raw_serial, str):
                continue
            try:
                normalized_items.add(normalize_battery_serial(raw_serial))
            except HTTPException:
                continue

        if normalized_serial not in normalized_items:
            continue

        candidate_from_type = (candidate_from_type or "").strip().lower()
        if candidate_from_type == "warehouse" and candidate_from_id is not None:
            return candidate_from_id
        if candidate_from_type == "shelf":
            warehouse_id = _resolve_warehouse_id_from_shelf(session, candidate_from_id)
            if warehouse_id is not None:
                return warehouse_id

    return None


def _resolve_warehouse_id_for_location(
    session: Session,
    *,
    battery_serial: str,
    location_type: Optional[str],
    location_id: Optional[int],
) -> Optional[int]:
    normalized_location_type = (location_type or "").strip().lower()
    if normalized_location_type == "warehouse" and location_id is not None:
        return location_id
    if normalized_location_type == "shelf":
        return _resolve_warehouse_id_from_shelf(session, location_id)
    if normalized_location_type == "station":
        return _resolve_warehouse_id_from_station_history(
            session,
            battery_serial=battery_serial,
            station_id=location_id,
        )
    return None


def _get_first_active_warehouse_id(session: Session) -> Optional[int]:
    return session.exec(
        select(Warehouse.id).where(Warehouse.is_active == True).order_by(Warehouse.id.asc()).limit(1)
    ).first()


def _resolve_return_delivery_warehouse_id(session: Session, battery: Battery, order: Order) -> int:
    normalized_serial = normalize_battery_serial(battery.serial_number)
    dispatch_event_description = _find_dispatch_event_description_for_order(
        session,
        battery_id=battery.id,
        order_id=order.id,
    )
    dispatch_location_type, dispatch_location_id = _extract_dispatch_source_from_event(dispatch_event_description)
    dispatch_warehouse_id = _resolve_warehouse_id_for_location(
        session,
        battery_serial=normalized_serial,
        location_type=dispatch_location_type,
        location_id=dispatch_location_id,
    )
    if dispatch_warehouse_id is not None:
        return dispatch_warehouse_id

    if order.original_order_id:
        original_dispatch_event_description = _find_dispatch_event_description_for_order(
            session,
            battery_id=battery.id,
            order_id=order.original_order_id,
        )
        original_location_type, original_location_id = _extract_dispatch_source_from_event(
            original_dispatch_event_description
        )
        original_warehouse_id = _resolve_warehouse_id_for_location(
            session,
            battery_serial=normalized_serial,
            location_type=original_location_type,
            location_id=original_location_id,
        )
        if original_warehouse_id is not None:
            return original_warehouse_id

    current_warehouse_id = _resolve_warehouse_id_for_location(
        session,
        battery_serial=normalized_serial,
        location_type=battery.location_type,
        location_id=battery.location_id,
    )
    if current_warehouse_id is not None:
        return current_warehouse_id

    fallback_warehouse_id = get_single_active_warehouse_id(session)
    if fallback_warehouse_id is not None:
        return fallback_warehouse_id

    default_active_warehouse_id = _get_first_active_warehouse_id(session)
    if default_active_warehouse_id is not None:
        logger.warning(
            "Return destination warehouse fallback used for battery=%s order_id=%s selected_warehouse_id=%s",
            normalized_serial,
            order.id,
            default_active_warehouse_id,
        )
        return default_active_warehouse_id

    raise HTTPException(
        status_code=409,
        detail=(
            f"Cannot resolve return destination warehouse for battery {battery.serial_number} on order {order.id}. "
            "No active warehouse resolution path found."
        ),
    )


def _sync_batteries_for_order_status(
    session: Session,
    order: Order,
    new_status: str,
    failure_reason: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> None:
    battery_ids = _get_order_battery_ids(session, order)
    batteries = _fetch_batteries_by_serials(session, battery_ids, for_update=True)

    for battery in batteries:
        serial = normalize_battery_serial(battery.serial_number)
        battery.serial_number = serial

        if new_status == "in_transit":
            source_location_type = battery.location_type
            source_location_id = battery.location_id

            if source_location_type not in {"warehouse", "station", "shelf", "customer"}:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Battery {serial} at location '{source_location_type}' cannot be dispatched. "
                        "Battery must be in warehouse/station/shelf/customer before dispatch."
                    ),
                )
            if source_location_type in {"warehouse", "station", "shelf"} and source_location_id is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Battery {serial} has missing location_id for '{source_location_type}'",
                )
            if source_location_type == "shelf":
                assert_battery_shelf_state_consistent(session, battery)

            apply_battery_transition(
                session,
                battery=battery,
                to_status="deployed",
                to_location_type="transit",
                to_location_id=None,
                event_type="dispatched",
                event_description=_build_dispatch_event_description(
                    order.id,
                    source_location_type,
                    source_location_id,
                ),
                actor_id=actor_id,
                exclude_order_id=order.id,
            )
        elif new_status == "delivered":
            if order.type == "return":
                warehouse_id = _resolve_return_delivery_warehouse_id(session, battery, order)
                apply_battery_transition(
                    session,
                    battery=battery,
                    to_status="available",
                    to_location_type="warehouse",
                    to_location_id=warehouse_id,
                    event_type="returned",
                    event_description=(
                        f"Returned to warehouse #{warehouse_id} via return order {order.id}"
                    ),
                    actor_id=actor_id,
                    exclude_order_id=order.id,
                )
            else:
                apply_battery_transition(
                    session,
                    battery=battery,
                    to_status="deployed",
                    to_location_type="customer",
                    to_location_id=None,
                    event_type="delivered",
                    event_description=f"Delivered with order {order.id}",
                    actor_id=actor_id,
                    exclude_order_id=order.id,
                )
        elif new_status in {"failed", "cancelled"}:
            restore_location_type, restore_location_id = _resolve_release_location_for_order(
                session,
                battery,
                order,
            )
            description = f"Released from order {order.id} due to {new_status}"
            if new_status == "failed" and failure_reason:
                description = f"{description}: {failure_reason}"
            apply_battery_transition(
                session,
                battery=battery,
                to_status="available",
                to_location_type=restore_location_type,
                to_location_id=restore_location_id,
                event_type="released",
                event_description=description,
                actor_id=actor_id,
                exclude_order_id=order.id,
            )
        else:
            continue


def _validate_status_transition(order: Order, new_status: str) -> None:
    current_status = _canonical_order_status(order.status)
    target_status = _canonical_order_status(new_status)

    if target_status not in VALID_ORDER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(VALID_ORDER_STATUSES)}",
        )

    allowed = VALID_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{current_status}' to '{target_status}'. Allowed: {sorted(allowed)}",
        )


def _validate_order_list_query_params(
    *,
    skip: int,
    limit: int,
    status: Optional[str],
    priority: Optional[str],
    sort_by: str,
    sort_order: str,
) -> tuple[Optional[str], Optional[str], str, str]:
    if skip < 0:
        raise HTTPException(status_code=400, detail="skip must be >= 0")
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

    normalized_status = _canonical_order_status(status) if status else None
    if normalized_status and normalized_status not in VALID_ORDER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Allowed: {sorted(VALID_ORDER_STATUSES)}",
        )

    normalized_priority = priority.strip().lower() if priority else None
    if normalized_priority and normalized_priority not in VALID_ORDER_PRIORITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid priority '{priority}'. Allowed: {sorted(VALID_ORDER_PRIORITIES)}",
        )

    normalized_sort_by = sort_by.strip().lower()
    if normalized_sort_by not in VALID_ORDER_SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by '{sort_by}'. Allowed: {sorted(VALID_ORDER_SORT_FIELDS)}",
        )

    normalized_sort_order = sort_order.strip().lower()
    if normalized_sort_order not in VALID_SORT_DIRECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_order '{sort_order}'. Allowed: {sorted(VALID_SORT_DIRECTIONS)}",
        )

    return (
        normalized_status,
        normalized_priority,
        normalized_sort_by,
        normalized_sort_order,
    )


@router.get(
    "/",
    response_model=DataResponseWithPagination[List[OrderRead]],
    response_model_exclude_none=True,
)
def get_orders(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    assigned_driver_id: Optional[str] = None,
    include_pagination: bool = False,
    sort_by: str = "order_date",
    sort_order: str = "desc",
    response: Response = None,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
):
    """Get all orders with pagination, filtering, and search."""
    (
        normalized_status,
        normalized_priority,
        normalized_sort_by,
        normalized_sort_order,
    ) = _validate_order_list_query_params(
        skip=skip,
        limit=limit,
        status=status,
        priority=priority,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    search_term_normalized = (search or "").strip() or None
    parsed_assigned_driver_id = _parse_driver_id(assigned_driver_id) if assigned_driver_id else None

    cache_key = _order_list_cache_key(
        {
            "skip": skip,
            "limit": limit,
            "status": normalized_status,
            "priority": normalized_priority,
            "search": search_term_normalized,
            "assigned_driver_id": parsed_assigned_driver_id,
            "include_pagination": include_pagination,
            "sort_by": normalized_sort_by,
            "sort_order": normalized_sort_order,
            "viewer_user_id": current_user.id,
        }
    )
    def _compute_payload() -> dict[str, Any]:
        query = select(Order)

        if normalized_status:
            query = query.where(Order.status.in_(_status_aliases_for(normalized_status)))
        if normalized_priority:
            query = query.where(Order.priority == normalized_priority)
        if parsed_assigned_driver_id is not None:
            query = query.where(Order.assigned_driver_id == parsed_assigned_driver_id)
        if search_term_normalized:
            like_term = f"%{search_term_normalized}%"
            query = query.where(
                Order.id.ilike(like_term)
                | Order.customer_name.ilike(like_term)
                | Order.destination.ilike(like_term)
                | Order.tracking_number.ilike(like_term)
            )

        total_count: Optional[int] = None
        if include_pagination:
            count_cache_key = _order_list_count_cache_key(
                {
                    "status": normalized_status,
                    "priority": normalized_priority,
                    "search": search_term_normalized,
                    "assigned_driver_id": parsed_assigned_driver_id,
                    "viewer_user_id": current_user.id,
                }
            )
            total_count = _order_list_count_cache_get(count_cache_key)
            if total_count is None:
                total_count = int(session.exec(select(func.count()).select_from(query.subquery())).one() or 0)
                _order_list_count_cache_set(count_cache_key, total_count)

        if normalized_sort_by == "updated_at":
            order_column = Order.updated_at
        elif normalized_sort_by == "estimated_delivery":
            order_column = Order.estimated_delivery
        else:
            order_column = Order.order_date

        if normalized_sort_order == "asc":
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())

        orders = session.exec(query.offset(skip).limit(limit)).all()

        pagination = None
        if include_pagination:
            resolved_total = int(total_count or 0)
            pagination = PaginationMeta(
                total=resolved_total,
                skip=skip,
                limit=limit,
                has_more=(skip + len(orders)) < resolved_total,
            )

        response_payload = DataResponseWithPagination(success=True, data=orders, pagination=pagination)
        return response_payload.model_dump(mode="json", exclude_none=True)

    result = DistributedCacheService.get_or_compute_json(
        cache_key=cache_key,
        ttl_seconds=_order_list_cache_ttl_seconds(),
        compute=_compute_payload,
        lock_ttl_seconds=_order_list_cache_lock_ttl_seconds(),
        lock_wait_ms=_order_list_cache_lock_wait_ms(),
        lock_poll_ms=_order_list_cache_lock_poll_ms(),
        ttl_jitter_seconds=_order_list_cache_ttl_jitter_seconds(),
        stale_ttl_seconds=_order_list_cache_stale_ttl_seconds(),
        allow_stale_on_error=True,
        log_label="orders_list",
    )
    if response is not None and settings.DEBUG:
        response.headers["X-Cache-Orders-List"] = result.source
    if isinstance(result.payload, dict):
        return DataResponseWithPagination.model_validate(result.payload)
    raise HTTPException(status_code=500, detail="Failed to build order list response")


@router.get("/{order_id}", response_model=DataResponse[OrderRead])
def get_order(
    order_id: str,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
):
    """Get order by ID."""
    order = _resolve_order_or_404(session, order_id)
    return DataResponse(success=True, data=order)


@router.post("/", response_model=DataResponse[OrderRead])
def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Create a new delivery order."""
    payload = _schema_to_dict(order_data)
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_fingerprint = build_request_fingerprint(payload)
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path="/orders",
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    if payload.get("units", 0) <= 0:
        raise HTTPException(status_code=400, detail="units must be greater than 0")

    order_id = payload.get("id") or f"ORD-{uuid.uuid4().hex[:6].upper()}"
    if session.get(Order, order_id):
        raise HTTPException(status_code=409, detail="Order ID already exists")

    payload["destination"] = _normalize_destination(payload.get("destination"))
    payload["customer_name"] = _normalize_customer_name(payload.get("customer_name"))
    payload["notes"] = _normalize_order_notes(payload.get("notes"))

    payload["customer_phone"] = _normalize_customer_phone(payload.get("customer_phone"))
    tracking_number = _normalize_tracking_number(payload.get("tracking_number"), order_id=order_id)
    _acquire_tracking_number_lock(session, tracking_number)
    tracking_conflict = session.exec(
        select(Order.id)
        .where(Order.tracking_number == tracking_number)
        .limit(1)
    ).first()
    if tracking_conflict and tracking_conflict != order_id:
        raise HTTPException(
            status_code=409,
            detail=f"tracking_number '{tracking_number}' is already in use",
        )
    payload["tracking_number"] = tracking_number

    payload["priority"] = _normalize_order_priority(payload.get("priority"))
    payload["total_value"] = _normalize_total_value(payload.get("total_value"))

    order_date = _normalize_order_datetime(payload.get("order_date"), field_name="order_date") or datetime.utcnow()
    dispatch_date = _normalize_order_datetime(payload.get("dispatch_date"), field_name="dispatch_date")
    estimated_delivery = _normalize_order_datetime(
        payload.get("estimated_delivery"),
        field_name="estimated_delivery",
    )
    if dispatch_date is not None and dispatch_date < order_date:
        raise HTTPException(status_code=400, detail="dispatch_date cannot be earlier than order_date")
    if estimated_delivery is not None:
        comparison_base = dispatch_date or order_date
        if estimated_delivery < comparison_base:
            raise HTTPException(
                status_code=400,
                detail="estimated_delivery cannot be earlier than order_date/dispatch_date",
            )
    payload["order_date"] = order_date
    payload["dispatch_date"] = dispatch_date
    payload["estimated_delivery"] = estimated_delivery
    payload["latitude"], payload["longitude"] = _normalize_order_coordinates(
        payload.get("latitude"),
        payload.get("longitude"),
    )

    requested_status = _canonical_order_status(payload.pop("status", "pending"))
    if requested_status not in VALID_ORDER_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(VALID_ORDER_STATUSES)}",
        )
    if requested_status != "pending":
        raise HTTPException(status_code=400, detail="New orders must start in 'pending' state")

    order_type = payload.get("type", "delivery")
    if order_type != "delivery":
        raise HTTPException(
            status_code=400,
            detail="Use /orders/{order_id}/return to create return orders",
        )
    payload["type"] = "delivery"
    payload["refund_status"] = "none"

    assigned_driver_id = payload.get("assigned_driver_id")
    assigned_driver: Optional[DriverProfile] = None
    if assigned_driver_id is not None:
        _assert_driver_available_for_order(session, assigned_driver_id, for_update=True)
        assigned_driver = session.get(DriverProfile, assigned_driver_id)

    payload["id"] = order_id
    payload["status"] = "pending"
    payload["updated_at"] = datetime.utcnow()

    assigned_battery_ids = _parse_assigned_battery_ids(payload.get("assigned_battery_ids"))
    if not assigned_battery_ids:
        raise HTTPException(
            status_code=400,
            detail="assigned_battery_ids is required to create a dispatch order",
        )
    if payload.get("units") != len(assigned_battery_ids):
        raise HTTPException(
            status_code=400,
            detail="units must exactly match the number of assigned_battery_ids",
        )
    payload["assigned_battery_ids"] = json.dumps(assigned_battery_ids) if assigned_battery_ids else None

    order = Order(**payload)
    _reserve_order_batteries(session, order, battery_ids=assigned_battery_ids)

    if assigned_driver_id is not None:
        _mark_order_assigned_if_pending(order)
        _set_driver_status(session, assigned_driver_id, "busy")

    session.add(order)
    try:
        session.flush()
        _persist_order_batteries(session, order.id, assigned_battery_ids)

        response = DataResponse(success=True, data=order)
        record_idempotent_response(
            session,
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method="POST",
            request_path="/orders",
            request_fingerprint=request_fingerprint,
            response_status_code=200,
            response_payload=response,
        )

        _emit_order_realtime_update(
            session=session,
            event_type="order_created",
            order=order,
            actor_user_id=current_user.id,
            request_idempotency_key=idempotency_key,
        )

        session.commit()
    except IntegrityError as exc:
        session.rollback()
        _raise_create_order_integrity_error(exc)
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Create-order database error order_id=%s", order_id)
        raise HTTPException(status_code=500, detail="Failed to create order")

    session.refresh(order)
    _auto_notify_order_created(
        session,
        order=order,
        assigned_driver=assigned_driver,
    )
    if assigned_driver is not None:
        _auto_notify_driver_assignment(
            session,
            order=order,
            driver=assigned_driver,
        )
    return DataResponse(success=True, data=order)


@router.put("/{order_id}/status", response_model=DataResponse[OrderRead])
def update_order_status(
    order_id: str,
    status_update: StatusUpdate,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Update order status."""
    status_payload = _schema_to_dict(status_update)
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/orders/{order_id}/status"
    request_fingerprint = build_request_fingerprint(status_payload)
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="PUT",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    order = _resolve_order_or_404(session, order_id)

    new_status = _canonical_order_status(status_update.status)
    _validate_status_transition(order, new_status)

    if new_status == "in_transit":
        if not order.assigned_driver_id:
            raise HTTPException(status_code=400, detail="Cannot dispatch order without an assigned driver")
        _assert_driver_available_for_order(
            session,
            order.assigned_driver_id,
            exclude_order_id=order.id,
            allow_busy=True,
        )
        order.dispatch_date = status_update.dispatch_date or datetime.utcnow()
        _set_driver_status(session, order.assigned_driver_id, "busy")

    if new_status == "failed" and not status_update.failure_reason:
        raise HTTPException(status_code=400, detail="failure_reason is required when marking an order as failed")

    if _canonical_order_status(order.status) == "failed" and new_status == "pending":
        _reserve_order_batteries(
            session,
            order,
            exclude_order_id=order.id,
        )
        if order.assigned_driver_id:
            _assert_driver_available_for_order(
                session,
                order.assigned_driver_id,
                exclude_order_id=order.id,
                allow_busy=True,
            )
            _set_driver_status(session, order.assigned_driver_id, "busy")

    order.status = new_status
    order.updated_at = datetime.utcnow()

    if new_status == "delivered":
        order.delivered_at = datetime.utcnow()
    if new_status == "failed":
        order.failure_reason = status_update.failure_reason

    _sync_batteries_for_order_status(
        session,
        order,
        new_status,
        status_update.failure_reason,
        actor_id=current_user.id,
    )

    if new_status in TERMINAL_STATUSES:
        _release_driver_if_idle(session, order)

    session.add(order)
    response = DataResponse(success=True, data=order)
    record_idempotent_response(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="PUT",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
        response_status_code=200,
        response_payload=response,
    )
    _emit_order_realtime_update(
        session=session,
        event_type="order_status_updated",
        order=order,
        actor_user_id=current_user.id,
        metadata={"new_status": new_status},
        request_idempotency_key=idempotency_key,
    )
    session.commit()
    session.refresh(order)
    _auto_notify_order_status_update(session, order, new_status)
    return DataResponse(success=True, data=order)


@router.post("/{order_id}/mark-in-transit", response_model=DataResponse[OrderRead])
def mark_in_transit(
    order_id: str,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
):
    """Mark order as in transit (dispatched)."""
    status_update = StatusUpdate(status="in_transit", dispatch_date=datetime.utcnow())
    return update_order_status(
        order_id=order_id,
        status_update=status_update,
        current_user=current_user,
        session=session,
        idempotency_key=None,
    )


@router.post("/{order_id}/mark-failed", response_model=DataResponse[OrderRead])
def mark_failed(
    order_id: str,
    failure_reason: str = Query(..., description="Reason for delivery failure"),
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
):
    """Mark order as failed with a reason and release assigned batteries."""
    status_update = StatusUpdate(status="failed", failure_reason=failure_reason)
    return update_order_status(
        order_id=order_id,
        status_update=status_update,
        current_user=current_user,
        session=session,
        idempotency_key=None,
    )


@router.post("/{order_id}/proof-of-delivery", response_model=DataResponse[OrderRead])
def submit_proof_of_delivery(
    order_id: str,
    pod: ProofOfDeliveryCreate,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Submit proof of delivery (image URL + notes) and mark order as delivered."""
    pod_payload = _schema_to_dict(pod)
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/orders/{order_id}/proof-of-delivery"
    request_fingerprint = build_request_fingerprint(pod_payload)
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    order = _resolve_order_or_404(session, order_id)

    previous_status = order.status
    canonical_status = _canonical_order_status(order.status)
    raw_status = str(order.status or "").strip().lower()

    # Legacy deployments may still keep an assigned/dispatched order out of canonical in_transit.
    # Accept those when a driver is attached, then normalize to delivered in this handler.
    allow_assigned_like_pod = raw_status in {"assigned", "new"} and order.assigned_driver_id is not None
    allow_dispatched_pending_pod = (
        canonical_status == "pending"
        and order.assigned_driver_id is not None
        and order.dispatch_date is not None
    )

    if canonical_status != "in_transit" and not allow_assigned_like_pod and not allow_dispatched_pending_pod:
        raise HTTPException(
            status_code=409,
            detail=(
                "Proof of delivery can only be submitted for in-transit/assigned dispatched orders. "
                f"Current status is '{order.status}'."
            ),
        )

    normalized_image_url = _normalize_pod_media_url(
        pod.image_url,
        field_name="image_url",
        required=True,
    )
    normalized_signature_url = _normalize_pod_media_url(
        pod.signature_url,
        field_name="signature_url",
        required=False,
    )

    normalized_notes = (str(pod.notes).strip() if pod.notes is not None else None) or None
    normalized_recipient_name = (str(pod.recipient_name).strip() if pod.recipient_name is not None else None) or None

    order.proof_of_delivery_url = normalized_image_url
    order.proof_of_delivery_notes = normalized_notes
    order.proof_of_delivery_signature_url = normalized_signature_url
    order.recipient_name = normalized_recipient_name
    order.proof_of_delivery_captured_at = datetime.utcnow()
    if order.dispatch_date is None:
        order.dispatch_date = datetime.utcnow()
    order.status = "delivered"
    order.delivered_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()

    _sync_batteries_for_order_status(
        session,
        order,
        "delivered",
        actor_id=current_user.id,
    )
    _release_driver_if_idle(session, order)

    session.add(order)
    response = DataResponse(success=True, data=order)
    record_idempotent_response(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
        response_status_code=200,
        response_payload=response,
    )
    _emit_order_realtime_update(
        session=session,
        event_type="order_status_updated",
        order=order,
        actor_user_id=current_user.id,
        metadata={
            "new_status": "delivered",
            "source": "proof_of_delivery",
            "previous_status": previous_status,
        },
        request_idempotency_key=idempotency_key,
    )
    session.commit()
    session.refresh(order)
    _auto_notify_order_status_update(session, order, "delivered")
    return response


@router.put("/{order_id}/assign-driver", response_model=DataResponse[OrderRead])
@router.post("/{order_id}/assign-driver", response_model=DataResponse[OrderRead], include_in_schema=False)
def assign_driver(
    order_id: str,
    driver_id: Optional[str] = Query(default=None),
    driver_id_legacy: Optional[str] = Query(default=None, alias="driverId"),
    assigned_driver_id_query: Optional[str] = Query(default=None, alias="assigned_driver_id"),
    assigned_driver_id_legacy_query: Optional[str] = Query(default=None, alias="assignedDriverId"),
    body: Optional[dict] = Body(default=None),
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Assign a driver to an order."""
    driver_reference = _extract_driver_reference(
        driver_id,
        body,
        query_aliases=[
            driver_id_legacy,
            assigned_driver_id_query,
            assigned_driver_id_legacy_query,
        ],
    )
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/orders/{order_id}/assign-driver"
    request_fingerprint = build_request_fingerprint({"driver_id": driver_reference})
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="PUT",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    role_names = _user_role_names(current_user)
    resolved_order_id: Optional[str] = None
    resolved_driver_id: Optional[int] = None
    previous_status: Optional[str] = None
    next_status: Optional[str] = None
    try:
        order = _resolve_order_for_assignment(session, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        resolved_order_id = order.id
        previous_status = order.status

        canonical_order_status = _canonical_order_status(order.status)
        if canonical_order_status in TERMINAL_STATUSES:
            logger.warning(
                "Assign-driver blocked terminal state order_ref=%s order_id=%s state=%s driver_ref=%s user_id=%s roles=%s",
                order_id,
                resolved_order_id,
                canonical_order_status,
                driver_reference,
                current_user.id,
                role_names,
            )
            raise HTTPException(
                status_code=409,
                detail=f"Cannot assign driver when order is in terminal state '{canonical_order_status}'",
            )

        driver = _resolve_driver_for_assignment(session, driver_reference)
        if not driver or driver.id is None:
            raise HTTPException(status_code=404, detail="Driver not found")
        resolved_driver_id = int(driver.id)

        if order.assigned_driver_id == resolved_driver_id:
            _mark_order_assigned_if_pending(order)
            session.add(order)
            logger.info(
                "Assign-driver idempotent order_ref=%s order_id=%s driver_ref=%s driver_id=%s user_id=%s roles=%s",
                order_id,
                resolved_order_id,
                driver_reference,
                resolved_driver_id,
                current_user.id,
                role_names,
            )
            response = DataResponse(success=True, data=order)
            record_idempotent_response(
                session,
                user_id=current_user.id,
                idempotency_key=idempotency_key,
                request_method="PUT",
                request_path=request_path,
                request_fingerprint=request_fingerprint,
                response_status_code=200,
                response_payload=response,
            )
            _emit_order_realtime_update(
                session=session,
                event_type="order_driver_assignment_confirmed",
                order=order,
                actor_user_id=current_user.id,
                metadata={"driver_id": resolved_driver_id, "idempotent": True},
                request_idempotency_key=idempotency_key,
            )
            session.commit()
            session.refresh(order)
            return response

        _assert_driver_available_for_order(
            session,
            resolved_driver_id,
            exclude_order_id=order.id,
            check_active_conflict=False,
            for_update=True,
        )

        previous_driver_id = order.assigned_driver_id
        reassigned_from_order: Optional[Order] = None

        conflicting_order = session.exec(
            select(Order)
            .where(
                Order.assigned_driver_id == resolved_driver_id,
                Order.id != order.id,
                Order.status.in_(ACTIVE_DRIVER_ORDER_STATUSES_DB),
            )
            .order_by(Order.updated_at.desc())
            .limit(1)
        ).first()
        if conflicting_order is not None:
            target_order_status = _canonical_order_status(order.status)
            conflicting_status = _canonical_order_status(conflicting_order.status)
            if target_order_status == "pending" and conflicting_status == "pending":
                reassigned_from_order = conflicting_order
                conflicting_order.assigned_driver_id = None
                if str(conflicting_order.status).strip().lower() == "assigned":
                    conflicting_order.status = "pending"
                conflicting_order.updated_at = datetime.utcnow()
                session.add(conflicting_order)
                _set_driver_status(session, resolved_driver_id, "available")
                logger.info(
                    "Assign-driver auto-reassigned pending driver_id=%s from_order_id=%s to_order_id=%s user_id=%s roles=%s",
                    resolved_driver_id,
                    conflicting_order.id,
                    order.id,
                    current_user.id,
                    role_names,
                )
            else:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Driver conflict: target order '{order.id}' is '{order.status}', "
                        f"but driver is already assigned to order '{conflicting_order.id}' "
                        f"with status '{conflicting_order.status}'"
                    ),
                )

        # Final guard after optional pending-order reassignment.
        _assert_driver_available_for_order(
            session,
            resolved_driver_id,
            exclude_order_id=order.id,
            for_update=True,
        )

        order.assigned_driver_id = resolved_driver_id
        order.updated_at = datetime.utcnow()
        _mark_order_assigned_if_pending(order)
        next_status = order.status

        _set_driver_status(session, resolved_driver_id, "busy")

        if previous_driver_id:
            active_order = session.exec(
                select(Order.id)
                .where(
                    Order.assigned_driver_id == previous_driver_id,
                    Order.id != order.id,
                    Order.status.in_(ACTIVE_DRIVER_ORDER_STATUSES_DB),
                )
                .limit(1)
            ).first()
            if not active_order:
                _set_driver_status(session, previous_driver_id, "available")

        session.add(order)
        response = DataResponse(success=True, data=order)
        record_idempotent_response(
            session,
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method="PUT",
            request_path=request_path,
            request_fingerprint=request_fingerprint,
            response_status_code=200,
            response_payload=response,
        )
        if reassigned_from_order is not None:
            _emit_order_realtime_update(
                session=session,
                event_type="order_driver_unassigned_reassign",
                order=reassigned_from_order,
                actor_user_id=current_user.id,
                metadata={
                    "driver_id": resolved_driver_id,
                    "reassigned_to_order_id": order.id,
                },
                request_idempotency_key=idempotency_key,
            )
        _emit_order_realtime_update(
            session=session,
            event_type="order_driver_assigned",
            order=order,
            actor_user_id=current_user.id,
            metadata={
                "driver_id": resolved_driver_id,
                "previous_driver_id": previous_driver_id,
                "reassigned_from_order_id": reassigned_from_order.id if reassigned_from_order else None,
                "idempotent": False,
            },
            request_idempotency_key=idempotency_key,
        )
        session.commit()
        if reassigned_from_order is not None:
            session.refresh(reassigned_from_order)
        session.refresh(order)
        _auto_notify_driver_assignment(
            session,
            order=order,
            driver=driver,
        )
        logger.info(
            "Assign-driver success order_ref=%s order_id=%s driver_ref=%s driver_id=%s previous_driver_id=%s user_id=%s roles=%s state_before=%s state_after=%s",
            order_id,
            resolved_order_id,
            driver_reference,
            resolved_driver_id,
            previous_driver_id,
            current_user.id,
            role_names,
            previous_status,
            next_status,
        )
        return response
    except HTTPException as exc:
        logger.warning(
            "Assign-driver rejected order_ref=%s order_id=%s driver_ref=%s driver_id=%s user_id=%s roles=%s state_before=%s state_after=%s status=%s detail=%s",
            order_id,
            resolved_order_id,
            driver_reference,
            resolved_driver_id,
            current_user.id,
            role_names,
            previous_status,
            next_status,
            exc.status_code,
            exc.detail,
        )
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        error_text = str(exc).lower()
        if "assigned_driver_id" in error_text and "foreign key" in error_text:
            logger.exception(
                "Assign-driver FK schema mismatch order_ref=%s order_id=%s driver_ref=%s driver_id=%s user_id=%s roles=%s",
                order_id,
                resolved_order_id,
                driver_reference,
                resolved_driver_id,
                current_user.id,
                role_names,
            )
            raise HTTPException(
                status_code=409,
                detail="Database schema mismatch for assigned_driver_id. Run latest migrations/fk-fix.",
            )
        logger.exception(
            "Assign-driver database error order_ref=%s order_id=%s driver_ref=%s driver_id=%s user_id=%s roles=%s state_before=%s state_after=%s",
            order_id,
            resolved_order_id,
            driver_reference,
            resolved_driver_id,
            current_user.id,
            role_names,
            previous_status,
            next_status,
        )
        raise HTTPException(status_code=500, detail="Failed to assign driver")
    except Exception:
        session.rollback()
        logger.exception(
            "Assign-driver unexpected error order_ref=%s order_id=%s driver_ref=%s driver_id=%s user_id=%s roles=%s state_before=%s state_after=%s",
            order_id,
            resolved_order_id,
            driver_reference,
            resolved_driver_id,
            current_user.id,
            role_names,
            previous_status,
            next_status,
        )
        raise HTTPException(status_code=500, detail="Failed to assign driver")


@router.put("/{order_id}/schedule", response_model=DataResponse[OrderRead])
def schedule_delivery(
    order_id: str,
    schedule: OrderSchedule,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Update scheduled delivery slot."""
    schedule_payload = _schema_to_dict(schedule)
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/orders/{order_id}/schedule"
    request_fingerprint = build_request_fingerprint(schedule_payload)
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="PUT",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    order = _resolve_order_or_404(session, order_id)
    if _canonical_order_status(order.status) in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Cannot reschedule order in '{order.status}' status")

    if schedule.scheduled_slot_end <= schedule.scheduled_slot_start:
        raise HTTPException(status_code=400, detail="scheduled_slot_end must be after scheduled_slot_start")

    order.scheduled_slot_start = schedule.scheduled_slot_start
    order.scheduled_slot_end = schedule.scheduled_slot_end
    order.updated_at = datetime.utcnow()

    session.add(order)
    response = DataResponse(success=True, data=order)
    record_idempotent_response(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="PUT",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
        response_status_code=200,
        response_payload=response,
    )
    session.commit()
    session.refresh(order)
    _auto_notify_order_rescheduled(session, order)
    return response


@router.post("/{order_id}/confirm-request", response_model=DataResponse[OrderRead])
def request_confirmation(
    order_id: str,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Trigger SMS to customer requesting confirmation."""
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/orders/{order_id}/confirm-request"
    request_fingerprint = build_request_fingerprint({"action": "confirm-request"})
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    order = _resolve_order_or_404(session, order_id)

    if not order.customer_phone:
        raise HTTPException(status_code=400, detail="Customer phone number is missing")

    link = _build_tracking_link(order)
    message = f"Hello {order.customer_name}, your Wezu delivery is scheduled. Please confirm here: {link}"

    success = _send_order_sms_with_tracking(
        session,
        order,
        title="Delivery Confirmation Requested",
        message=message,
        notification_type="order_confirmation",
        category="transactional",
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send SMS")

    order.confirmation_sent_at = datetime.utcnow()
    session.add(order)
    response = DataResponse(success=True, data=order)
    record_idempotent_response(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
        response_status_code=200,
        response_payload=response,
    )
    session.commit()
    session.refresh(order)
    return response


@router.post("/{order_id}/notify", response_model=DataResponse[dict])
def send_notification(
    order_id: str,
    type: str = Query(..., description="Notification type: out_for_delivery, delayed, etc."),
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Send a status notification SMS."""
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/orders/{order_id}/notify"
    request_fingerprint = build_request_fingerprint({"type": type})
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    order = _resolve_order_or_404(session, order_id)

    if not order.customer_phone:
        raise HTTPException(status_code=400, detail="Order has no phone number")

    if type == "out_for_delivery":
        message = f"Your order {order.id} is out for delivery! Track it here: {_build_tracking_link(order)}"
    elif type == "delayed":
        message = f"Sorry, your order {order.id} is slightly delayed. We will update you shortly."
    else:
        message = f"Update on order {order.id}: {type.replace('_', ' ').title()}"

    success = _send_order_sms_with_tracking(
        session,
        order,
        title="Order Status Update",
        message=message,
        notification_type=type,
        category="transactional",
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send SMS")
    response = DataResponse(success=True, data={"message": "Notification sent", "type": type})
    record_idempotent_response(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
        response_status_code=200,
        response_payload=response,
    )
    session.commit()
    return response


@router.post("/{order_id}/return", response_model=DataResponse[OrderRead])
def initiate_return(
    order_id: str,
    reason: str = Query(..., description="Reason for return"),
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Initiate a return for a delivered order."""
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/orders/{order_id}/return"
    request_fingerprint = build_request_fingerprint({"reason": reason})
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    original_order = _resolve_order_or_404(session, order_id, detail="Original order not found")

    if _canonical_order_status(original_order.status) != "delivered":
        raise HTTPException(status_code=400, detail="Can only return delivered orders")

    existing_open_return = session.exec(
        select(Order.id)
        .where(
            Order.type == "return",
            Order.original_order_id == original_order.id,
            Order.status.in_(ACTIVE_DRIVER_ORDER_STATUSES_DB),
        )
        .limit(1)
    ).first()
    if existing_open_return:
        raise HTTPException(status_code=400, detail="An active return already exists for this order")

    original_battery_ids = _get_order_battery_ids(session, original_order)

    return_id = f"RET-{uuid.uuid4().hex[:6].upper()}"
    return_order = Order(
        id=return_id,
        status="pending",
        type="return",
        original_order_id=original_order.id,
        refund_status="pending",
        customer_name=original_order.customer_name,
        customer_phone=original_order.customer_phone,
        destination=original_order.destination,
        units=original_order.units,
        total_value=original_order.total_value,
        notes=f"Return for order {original_order.id}. Reason: {reason}",
        priority=original_order.priority,
        order_date=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        assigned_battery_ids=json.dumps(original_battery_ids) if original_battery_ids else None,
    )

    for battery in _fetch_batteries_by_serials(
        session,
        original_battery_ids,
    ):
        _log_battery_event(
            session,
            battery.id,
            "return_initiated",
            f"Return initiated for order {original_order.id}. Return ID: {return_id}. Reason: {reason}",
            actor_id=current_user.id,
        )

    session.add(return_order)
    session.flush()
    _persist_order_batteries(session, return_order.id, original_battery_ids)
    response = DataResponse(success=True, data=return_order)
    record_idempotent_response(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
        response_status_code=200,
        response_payload=response,
    )
    session.commit()
    session.refresh(return_order)
    return response


@router.post("/{order_id}/refund", response_model=DataResponse[OrderRead])
def process_refund(
    order_id: str,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Process refund for a completed return order with financial settlement."""
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/orders/{order_id}/refund"
    request_fingerprint = build_request_fingerprint({"action": "process-refund"})
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return DataResponse(**replay_payload)

    order = _resolve_order_or_404(session, order_id)

    if order.type != "return":
        raise HTTPException(status_code=400, detail="Order is not a return order")

    if _canonical_order_status(order.status) != "delivered":
        raise HTTPException(status_code=400, detail="Refund can only be processed after return delivery is completed")

    if order.refund_status == "processed":
        raise HTTPException(status_code=400, detail="Refund already processed")

    if order.refund_status == "none":
        raise HTTPException(status_code=400, detail="Return order is not marked for refund")

    refund_amount = Decimal(str(order.total_value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if refund_amount <= 0:
        raise HTTPException(status_code=400, detail="Refund amount must be greater than zero")

    original_order = session.get(Order, order.original_order_id) if order.original_order_id else None
    customer_user = _resolve_customer_user(session, original_order or order)

    source_txn = session.exec(
        select(Transaction)
        .where(Transaction.reference_type.in_(["logistics_order", "order", "catalog_order"]))
        .where(Transaction.reference_id.in_([str(order.id), str(order.original_order_id or "")]))
        .order_by(Transaction.created_at.desc())
    ).first()

    refund_record: Optional[Refund] = None
    if source_txn:
        refund_record = session.exec(
            select(Refund)
            .where(Refund.transaction_id == source_txn.id)
            .order_by(Refund.created_at.desc())
        ).first()

    if source_txn and source_txn.razorpay_payment_id:
        try:
            gateway_refund = PaymentService.refund_transaction(
                source_txn.razorpay_payment_id,
                float(refund_amount),
            )
            gateway_refund_id = gateway_refund.get("id")
            if not refund_record:
                refund_record = Refund(
                    transaction_id=source_txn.id,
                    amount=refund_amount,
                    reason=f"Return refund for order {order.id}",
                    status="processed",
                    gateway_refund_id=gateway_refund_id,
                    processed_at=datetime.utcnow(),
                )
                session.add(refund_record)
            else:
                refund_record.amount = refund_amount
                refund_record.status = "processed"
                refund_record.gateway_refund_id = gateway_refund_id
                refund_record.processed_at = datetime.utcnow()
                session.add(refund_record)
            order.refund_status = "processed"
        except HTTPException:
            if refund_record:
                refund_record.status = "failed"
                session.add(refund_record)
            order.refund_status = "failed"
            order.updated_at = datetime.utcnow()
            session.add(order)
            session.commit()
            if customer_user:
                WorkflowAutomationService.notify_order_refund_outcome(
                    session,
                    user_id=customer_user.id,
                    order_id=str(order.id),
                    amount=refund_amount,
                    success=False,
                )
            raise
    elif customer_user:
        wallet = WalletService.get_wallet(
            session,
            customer_user.id,
            for_update=True,
            auto_commit_if_created=False,
        )
        wallet.balance = WalletService._to_money(wallet.balance) + WalletService._to_money(refund_amount)
        wallet.updated_at = datetime.utcnow()
        session.add(wallet)

        wallet_refund_txn = Transaction(
            wallet_id=wallet.id,
            amount=WalletService._to_money(refund_amount),
            balance_after=WalletService._to_money(wallet.balance),
            type="credit",
            category="refund",
            status="success",
            description=f"Return refund for logistics order {order.id}",
            reference_type="logistics_order",
            reference_id=str(order.id),
        )
        session.add(wallet_refund_txn)
        session.flush()

        refund_record = Refund(
            transaction_id=wallet_refund_txn.id,
            amount=refund_amount,
            reason=f"Return refund for order {order.id}",
            status="processed",
            processed_at=datetime.utcnow(),
        )
        session.add(refund_record)
        order.refund_status = "processed"
    else:
        order.refund_status = "failed"
        order.updated_at = datetime.utcnow()
        session.add(order)
        session.commit()
        raise HTTPException(
            status_code=409,
            detail="Unable to determine refund destination or payment source for this return order",
        )

    order.updated_at = datetime.utcnow()

    session.add(order)
    response = DataResponse(success=True, data=order)
    record_idempotent_response(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
        response_status_code=200,
        response_payload=response,
    )
    session.commit()
    session.refresh(order)
    if customer_user:
        WorkflowAutomationService.notify_order_refund_outcome(
            session,
            user_id=customer_user.id,
            order_id=str(order.id),
            amount=refund_amount,
            success=order.refund_status == "processed",
        )
    return response
