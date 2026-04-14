from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha1
import json
import logging
from typing import Any, Callable, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.models.analytics_dashboard import AnalyticsActivityEvent
from app.models.battery import BatteryLifecycleEvent
from app.models.inventory import InventoryTransfer, StockDiscrepancy
from app.models.order import Order
from app.repositories.analytics_dashboard_repository import AnalyticsDashboardRepository
from app.services.distributed_cache_service import DistributedCacheService
from app.services.redis_service import RedisService


ALLOWED_ACTIVITY_EVENT_TYPES = {
    "orderCreated",
    "shipmentInTransit",
    "orderDelivered",
    "batteryReceived",
    "batteryFault",
    "inventoryAudit",
    "batterySwapped",
    "lowInventory",
}

REPORT_SECTION_VALUES = ("kpis", "recent_activity", "orders", "inventory", "fleet")
_CACHE_DATETIME_MARKER = "__wezu_datetime__"
logger = logging.getLogger(__name__)


def _canonical_order_status(raw_status: Optional[str]) -> str:
    if not raw_status:
        return ""
    normalized = str(raw_status).strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "pending": "pending",
        "assigned": "pending",
        "new": "pending",
        "in_transit": "in_transit",
        "inprogress": "in_transit",
        "in_progress": "in_transit",
        "out_for_delivery": "in_transit",
        "outfordelivery": "in_transit",
        "dispatched": "in_transit",
        "delivered": "delivered",
        "completed": "delivered",
        "complete": "delivered",
        "done": "delivered",
        "failed": "failed",
        "failure": "failed",
        "delivery_failed": "failed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    }
    compact = normalized.replace("_", "")
    if compact in {"inprogress", "outfordelivery"}:
        return "in_transit"
    return mapping.get(normalized, mapping.get(compact, normalized))


def _parse_event_types_csv(raw_event_types: Optional[str]) -> Optional[set[str]]:
    if raw_event_types is None:
        return None
    tokens = [token.strip() for token in raw_event_types.split(",") if token.strip()]
    if not tokens:
        return None
    unknown = sorted(set(tokens) - ALLOWED_ACTIVITY_EVENT_TYPES)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported event_types: {unknown}. Allowed: {sorted(ALLOWED_ACTIVITY_EVENT_TYPES)}",
        )
    return set(tokens)


def resolve_timezone_or_400(timezone_name: Optional[str]) -> ZoneInfo:
    tz_name = (timezone_name or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timezone '{tz_name}'") from exc


def normalize_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _ensure_valid_window(from_utc: Optional[datetime], to_utc: Optional[datetime]) -> None:
    if from_utc is not None and to_utc is not None and from_utc > to_utc:
        raise HTTPException(status_code=400, detail="'from' must be earlier than or equal to 'to'")


def _to_timezone(dt_utc_naive: datetime, tz: ZoneInfo) -> datetime:
    return dt_utc_naive.replace(tzinfo=timezone.utc).astimezone(tz)


def _is_in_window(timestamp_utc_naive: datetime, *, from_utc: Optional[datetime], to_utc: Optional[datetime]) -> bool:
    if from_utc is not None and timestamp_utc_naive < from_utc:
        return False
    if to_utc is not None and timestamp_utc_naive > to_utc:
        return False
    return True


def _event_id(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    digest = sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"evt_{digest}"


def _serialize_for_cache(value: Any) -> Any:
    if isinstance(value, datetime):
        return {_CACHE_DATETIME_MARKER: value.isoformat()}
    if isinstance(value, dict):
        return {str(key): _serialize_for_cache(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_for_cache(item) for item in value]
    return value


def _deserialize_from_cache(value: Any) -> Any:
    if isinstance(value, dict):
        marker = value.get(_CACHE_DATETIME_MARKER)
        if isinstance(marker, str):
            try:
                return datetime.fromisoformat(marker)
            except Exception:
                return marker
        return {key: _deserialize_from_cache(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deserialize_from_cache(item) for item in value]
    return value


def _day_window_utc(now_utc: datetime, tz: ZoneInfo) -> tuple[datetime, datetime]:
    local_now = _to_timezone(now_utc, tz)
    local_day_start = datetime(
        year=local_now.year,
        month=local_now.month,
        day=local_now.day,
        tzinfo=tz,
    )
    local_day_end = local_day_start + timedelta(days=1)
    return (
        local_day_start.astimezone(timezone.utc).replace(tzinfo=None),
        local_day_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _month_start_utc(now_utc: datetime, tz: ZoneInfo) -> datetime:
    local_now = _to_timezone(now_utc, tz)
    local_month_start = datetime(
        year=local_now.year,
        month=local_now.month,
        day=1,
        tzinfo=tz,
    )
    return local_month_start.astimezone(timezone.utc).replace(tzinfo=None)


def _local_date_key(dt_utc_naive: datetime, tz: ZoneInfo) -> str:
    return _to_timezone(dt_utc_naive, tz).date().isoformat()


def _map_battery_lifecycle_event_type(raw_event_type: Optional[str]) -> Optional[str]:
    normalized = (raw_event_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    if "swap" in normalized:
        return "batterySwapped"
    if any(token in normalized for token in ("fault", "damage", "fail", "maintenance")):
        return "batteryFault"
    if any(
        token in normalized
        for token in ("receive", "received", "returned", "intake", "transfer_received", "created")
    ):
        return "batteryReceived"
    if any(token in normalized for token in ("audit", "reconcile", "reconciliation")):
        return "inventoryAudit"
    return None


@dataclass
class _ActivityEvent:
    id: str
    type: str
    title: str
    timestamp_utc: datetime
    reference_id: Optional[str]
    meta: Optional[dict[str, Any]]


class AnalyticsDashboardService:
    DASHBOARD_CACHE_NAMESPACE = "wezu:analytics:dashboard:v1"
    RECENT_ACTIVITY_CACHE_NAMESPACE = "wezu:analytics:recent_activity:v1"
    DASHBOARD_SNAPSHOT_NAMESPACE = "wezu:analytics:dashboard_snapshot:v1"
    DASHBOARD_SNAPSHOT_ACTIVITY_NAMESPACE = "wezu:analytics:dashboard_snapshot_activity:v1"
    DASHBOARD_SNAPSHOT_REFRESH_TRACK_NAMESPACE = "wezu:analytics:dashboard_snapshot_refresh:v1"

    @staticmethod
    def _dashboard_cache_ttl_seconds() -> int:
        raw = int(getattr(settings, "ANALYTICS_DASHBOARD_CACHE_TTL_SECONDS", 5) or 5)
        return max(1, min(30, raw))

    @staticmethod
    def _recent_activity_cache_ttl_seconds() -> int:
        raw = int(getattr(settings, "ANALYTICS_RECENT_ACTIVITY_CACHE_TTL_SECONDS", 5) or 5)
        return max(1, min(30, raw))

    @staticmethod
    def _recent_activity_default_lookback_days() -> int:
        raw = int(getattr(settings, "ANALYTICS_RECENT_ACTIVITY_DEFAULT_LOOKBACK_DAYS", 30) or 30)
        return max(1, min(365, raw))

    @staticmethod
    def _recent_activity_bounded_page_limit() -> int:
        raw = int(getattr(settings, "ANALYTICS_RECENT_ACTIVITY_BOUNDED_PAGE_LIMIT", 50) or 50)
        return max(10, min(200, raw))

    @staticmethod
    def _recent_activity_source_multiplier() -> int:
        raw = int(getattr(settings, "ANALYTICS_RECENT_ACTIVITY_SOURCE_MULTIPLIER", 12) or 12)
        return max(4, min(60, raw))

    @staticmethod
    def _recent_activity_max_source_rows() -> int:
        raw = int(getattr(settings, "ANALYTICS_RECENT_ACTIVITY_MAX_SOURCE_ROWS", 1200) or 1200)
        return max(100, min(5000, raw))

    @staticmethod
    def _recent_activity_source_row_budget(*, skip: int, limit: int) -> Optional[int]:
        # Fast-path common dashboard usage (first page) with bounded per-source reads.
        if skip > 0:
            return None
        if limit > AnalyticsDashboardService._recent_activity_bounded_page_limit():
            return None
        multiplier = AnalyticsDashboardService._recent_activity_source_multiplier()
        budget = max(80, limit * multiplier)
        return min(budget, AnalyticsDashboardService._recent_activity_max_source_rows())

    @staticmethod
    def _cache_lock_ttl_seconds() -> int:
        raw = int(getattr(settings, "ANALYTICS_CACHE_LOCK_TTL_SECONDS", 5) or 5)
        return max(1, min(20, raw))

    @staticmethod
    def _cache_lock_wait_ms() -> int:
        raw = int(getattr(settings, "ANALYTICS_CACHE_LOCK_WAIT_MS", 1200) or 1200)
        return max(0, min(10000, raw))

    @staticmethod
    def _cache_lock_poll_ms() -> int:
        raw = int(getattr(settings, "ANALYTICS_CACHE_LOCK_POLL_MS", 50) or 50)
        return max(10, min(500, raw))

    @staticmethod
    def _cache_ttl_jitter_seconds() -> int:
        raw = int(getattr(settings, "ANALYTICS_CACHE_TTL_JITTER_SECONDS", 2) or 2)
        return max(0, min(30, raw))

    @staticmethod
    def _cache_stale_ttl_seconds() -> int:
        raw = int(getattr(settings, "ANALYTICS_CACHE_STALE_TTL_SECONDS", 90) or 90)
        return max(0, min(900, raw))

    @staticmethod
    def _low_inventory_cache_ttl_seconds() -> int:
        raw = int(getattr(settings, "ANALYTICS_LOW_INVENTORY_CACHE_TTL_SECONDS", 15) or 15)
        return max(5, min(120, raw))

    @staticmethod
    def _snapshot_refresh_enabled() -> bool:
        return bool(getattr(settings, "ANALYTICS_DASHBOARD_SNAPSHOT_REFRESH_ENABLED", True))

    @staticmethod
    def _snapshot_refresh_interval_seconds() -> int:
        raw = int(getattr(settings, "ANALYTICS_DASHBOARD_SNAPSHOT_REFRESH_SECONDS", 60) or 60)
        return max(30, min(900, raw))

    @staticmethod
    def _snapshot_ttl_seconds() -> int:
        default_ttl = AnalyticsDashboardService._snapshot_refresh_interval_seconds() * 6
        raw = int(getattr(settings, "ANALYTICS_DASHBOARD_SNAPSHOT_TTL_SECONDS", default_ttl) or default_ttl)
        return max(15, min(300, raw))

    @staticmethod
    def _snapshot_timezones() -> list[str]:
        configured = str(getattr(settings, "ANALYTICS_DASHBOARD_SNAPSHOT_TIMEZONES", "UTC") or "UTC")
        candidates = [token.strip() for token in configured.split(",") if token.strip()]
        if settings.SCHEDULER_TIMEZONE:
            candidates.append(str(settings.SCHEDULER_TIMEZONE).strip())
        candidates.append("UTC")

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                deduped.append(candidate)
        return deduped

    @staticmethod
    def _snapshot_active_window_seconds() -> int:
        default_window = AnalyticsDashboardService._snapshot_refresh_interval_seconds() * 12
        raw = int(
            getattr(
                settings,
                "ANALYTICS_DASHBOARD_SNAPSHOT_ACTIVE_WINDOW_SECONDS",
                default_window,
            )
            or default_window
        )
        return max(30, min(1800, raw))

    @staticmethod
    def _snapshot_min_refresh_gap_seconds() -> int:
        default_gap = AnalyticsDashboardService._snapshot_refresh_interval_seconds() * 3
        raw = int(
            getattr(
                settings,
                "ANALYTICS_DASHBOARD_SNAPSHOT_MIN_REFRESH_GAP_SECONDS",
                default_gap,
            )
            or default_gap
        )
        return max(5, min(300, raw))

    @staticmethod
    def _snapshot_max_timezones_per_cycle() -> int:
        raw = int(getattr(settings, "ANALYTICS_DASHBOARD_SNAPSHOT_MAX_TIMEZONES_PER_CYCLE", 1) or 1)
        return max(1, min(10, raw))

    @staticmethod
    def _cache_key(namespace: str, payload: dict[str, Any]) -> str:
        return DistributedCacheService.build_key(namespace, payload)

    @staticmethod
    def _snapshot_cache_key(timezone_name: str) -> str:
        return AnalyticsDashboardService._cache_key(
            AnalyticsDashboardService.DASHBOARD_SNAPSHOT_NAMESPACE,
            {"timezone": timezone_name},
        )

    @staticmethod
    def _snapshot_activity_key() -> str:
        return AnalyticsDashboardService._cache_key(
            AnalyticsDashboardService.DASHBOARD_SNAPSHOT_ACTIVITY_NAMESPACE,
            {"kind": "active_timezones"},
        )

    @staticmethod
    def _snapshot_last_refresh_key(timezone_name: str) -> str:
        return AnalyticsDashboardService._cache_key(
            AnalyticsDashboardService.DASHBOARD_SNAPSHOT_REFRESH_TRACK_NAMESPACE,
            {"timezone": timezone_name},
        )

    @staticmethod
    def _cache_get(cache_key: str) -> Any | None:
        return DistributedCacheService.get_json(cache_key, decoder=_deserialize_from_cache)

    @staticmethod
    def _cache_set(cache_key: str, payload: Any, *, ttl_seconds: int) -> None:
        DistributedCacheService.set_json(
            cache_key,
            payload,
            ttl_seconds=ttl_seconds,
            encoder=_serialize_for_cache,
            ttl_jitter_seconds=AnalyticsDashboardService._cache_ttl_jitter_seconds(),
        )

    @staticmethod
    def _get_materialized_snapshot(timezone_name: str) -> dict[str, Any] | None:
        cache_key = AnalyticsDashboardService._snapshot_cache_key(timezone_name)
        payload = AnalyticsDashboardService._cache_get(cache_key)
        if isinstance(payload, dict):
            return payload
        return None

    @staticmethod
    def _set_materialized_snapshot(timezone_name: str, payload: dict[str, Any]) -> None:
        cache_key = AnalyticsDashboardService._snapshot_cache_key(timezone_name)
        AnalyticsDashboardService._cache_set(
            cache_key,
            payload,
            ttl_seconds=AnalyticsDashboardService._snapshot_ttl_seconds(),
        )

    @staticmethod
    def _touch_snapshot_activity(timezone_name: str) -> None:
        client = RedisService.get_client()
        if client is None:
            return

        key = AnalyticsDashboardService._snapshot_activity_key()
        active_window_seconds = AnalyticsDashboardService._snapshot_active_window_seconds()
        max_entries = max(4, AnalyticsDashboardService._snapshot_max_timezones_per_cycle() * 4)

        existing: list[str] = []
        try:
            raw = client.get(key)
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                parsed = json.loads(raw) if isinstance(raw, str) else []
                if isinstance(parsed, list):
                    existing = [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            existing = []

        updated = [timezone_name] + [tz for tz in existing if tz != timezone_name]
        if len(updated) > max_entries:
            updated = updated[:max_entries]

        try:
            client.setex(
                key,
                active_window_seconds,
                json.dumps(updated, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception:
            logger.exception("Failed to update analytics snapshot activity timezone=%s", timezone_name)

    @staticmethod
    def _active_snapshot_timezones() -> list[str]:
        client = RedisService.get_client()
        if client is None:
            return AnalyticsDashboardService._snapshot_timezones()[: AnalyticsDashboardService._snapshot_max_timezones_per_cycle()]

        key = AnalyticsDashboardService._snapshot_activity_key()
        try:
            raw = client.get(key)
            if not raw:
                return []
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            parsed = json.loads(raw) if isinstance(raw, str) else []
            if not isinstance(parsed, list):
                return []
            return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            logger.exception("Failed to read analytics snapshot activity")
            return []

    @staticmethod
    def _snapshot_refreshed_recently(timezone_name: str, *, now_utc: datetime) -> bool:
        client = RedisService.get_client()
        if client is None:
            return False

        key = AnalyticsDashboardService._snapshot_last_refresh_key(timezone_name)
        try:
            raw = client.get(key)
            if raw is None:
                return False
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            refreshed_epoch = float(raw)
            return (now_utc.timestamp() - refreshed_epoch) < AnalyticsDashboardService._snapshot_min_refresh_gap_seconds()
        except Exception:
            return False

    @staticmethod
    def _mark_snapshot_refreshed(timezone_name: str, *, now_utc: datetime) -> None:
        client = RedisService.get_client()
        if client is None:
            return

        key = AnalyticsDashboardService._snapshot_last_refresh_key(timezone_name)
        ttl_seconds = max(
            30,
            AnalyticsDashboardService._snapshot_min_refresh_gap_seconds() * 4,
        )
        try:
            client.setex(key, ttl_seconds, str(now_utc.timestamp()))
        except Exception:
            logger.exception("Failed to track analytics snapshot refresh timezone=%s", timezone_name)

    @staticmethod
    def _cached_compute(
        *,
        cache_key: str,
        ttl_seconds: int,
        compute: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        result = DistributedCacheService.get_or_compute_json(
            cache_key=cache_key,
            ttl_seconds=ttl_seconds,
            compute=compute,
            lock_ttl_seconds=AnalyticsDashboardService._cache_lock_ttl_seconds(),
            lock_wait_ms=AnalyticsDashboardService._cache_lock_wait_ms(),
            lock_poll_ms=AnalyticsDashboardService._cache_lock_poll_ms(),
            ttl_jitter_seconds=AnalyticsDashboardService._cache_ttl_jitter_seconds(),
            stale_ttl_seconds=AnalyticsDashboardService._cache_stale_ttl_seconds(),
            allow_stale_on_error=True,
            encoder=_serialize_for_cache,
            decoder=_deserialize_from_cache,
            log_label="analytics",
        )
        if isinstance(result.payload, dict):
            return result.payload
        raise ValueError(f"Unexpected analytics cache payload type for key={cache_key}")

    @staticmethod
    def _cached_low_inventory_counts(
        session: Session,
        *,
        threshold: int = 5,
    ) -> list[dict[str, Any]]:
        cache_key = AnalyticsDashboardService._cache_key(
            "wezu:analytics:low_inventory:v1",
            {"threshold": threshold},
        )
        result = DistributedCacheService.get_or_compute_json(
            cache_key=cache_key,
            ttl_seconds=AnalyticsDashboardService._low_inventory_cache_ttl_seconds(),
            compute=lambda: AnalyticsDashboardRepository.fetch_low_inventory_counts(
                session,
                threshold=threshold,
            ),
            lock_ttl_seconds=AnalyticsDashboardService._cache_lock_ttl_seconds(),
            lock_wait_ms=min(AnalyticsDashboardService._cache_lock_wait_ms(), 600),
            lock_poll_ms=AnalyticsDashboardService._cache_lock_poll_ms(),
            ttl_jitter_seconds=AnalyticsDashboardService._cache_ttl_jitter_seconds(),
            stale_ttl_seconds=max(30, AnalyticsDashboardService._cache_stale_ttl_seconds()),
            allow_stale_on_error=True,
            log_label="analytics_low_inventory",
        )
        if isinstance(result.payload, list):
            return [row for row in result.payload if isinstance(row, dict)]
        return []

    @staticmethod
    def refresh_materialized_snapshots(
        session: Session,
        *,
        timezone_names: Sequence[str] | None = None,
    ) -> dict[str, int]:
        if not AnalyticsDashboardService._snapshot_refresh_enabled():
            return {"requested": 0, "refreshed": 0, "failed": 0}

        if timezone_names is None:
            targets = AnalyticsDashboardService._active_snapshot_timezones()
            max_targets = AnalyticsDashboardService._snapshot_max_timezones_per_cycle()
            if len(targets) > max_targets:
                targets = targets[:max_targets]
        else:
            targets = list(timezone_names)

        summary = {"requested": len(targets), "refreshed": 0, "failed": 0}
        now_utc = datetime.utcnow()

        for timezone_name in targets:
            try:
                # Validate timezone and canonicalize behavior before snapshot refresh.
                resolve_timezone_or_400(timezone_name)
                if timezone_names is None and AnalyticsDashboardService._snapshot_refreshed_recently(
                    timezone_name,
                    now_utc=now_utc,
                ):
                    continue
                payload = AnalyticsDashboardService.build_dashboard_payload(
                    session,
                    timezone_name=timezone_name,
                    now_utc=now_utc,
                    _cache_bypass=True,
                )
                AnalyticsDashboardService._set_materialized_snapshot(timezone_name, payload)

                # Also warm short-lived request cache key for immediate reads.
                request_cache_key = AnalyticsDashboardService._cache_key(
                    AnalyticsDashboardService.DASHBOARD_CACHE_NAMESPACE,
                    {"timezone": timezone_name},
                )
                AnalyticsDashboardService._cache_set(
                    request_cache_key,
                    payload,
                    ttl_seconds=AnalyticsDashboardService._dashboard_cache_ttl_seconds(),
                )
                if timezone_names is None:
                    AnalyticsDashboardService._mark_snapshot_refreshed(timezone_name, now_utc=now_utc)
                summary["refreshed"] += 1
            except Exception:
                summary["failed"] += 1
                logger.exception(
                    "Analytics dashboard snapshot refresh failed timezone=%s",
                    timezone_name,
                )
        return summary

    @staticmethod
    def build_dashboard_payload(
        session: Session,
        *,
        timezone_name: str = "UTC",
        now_utc: Optional[datetime] = None,
        _cache_bypass: bool = False,
    ) -> dict[str, Any]:
        if now_utc is None and not _cache_bypass:
            AnalyticsDashboardService._touch_snapshot_activity(timezone_name)
            snapshot_payload = AnalyticsDashboardService._get_materialized_snapshot(timezone_name)
            if isinstance(snapshot_payload, dict):
                return snapshot_payload

            cache_key = AnalyticsDashboardService._cache_key(
                AnalyticsDashboardService.DASHBOARD_CACHE_NAMESPACE,
                {"timezone": timezone_name},
            )
            return AnalyticsDashboardService._cached_compute(
                cache_key=cache_key,
                ttl_seconds=AnalyticsDashboardService._dashboard_cache_ttl_seconds(),
                compute=lambda: AnalyticsDashboardService.build_dashboard_payload(
                    session,
                    timezone_name=timezone_name,
                    now_utc=datetime.utcnow(),
                    _cache_bypass=True,
                ),
            )

        tz = resolve_timezone_or_400(timezone_name)
        now = normalize_utc_naive(now_utc) or datetime.utcnow()
        day_start_utc, day_end_utc = _day_window_utc(now, tz)
        month_start_utc = _month_start_utc(now, tz)

        battery_kpis = AnalyticsDashboardRepository.fetch_battery_kpis(session)
        pending_orders = AnalyticsDashboardRepository.fetch_pending_orders(session)
        transfer_kpis = AnalyticsDashboardRepository.fetch_transfer_kpis(
            session,
            day_start_utc=day_start_utc,
            day_end_utc=day_end_utc,
            month_start_utc=month_start_utc,
            now_utc=now,
        )
        revenue = AnalyticsDashboardRepository.fetch_revenue_for_window(
            session,
            window_start_utc=month_start_utc,
            window_end_utc=now,
        )

        # Trend baseline (yesterday sent count, same timezone boundary logic).
        yesterday_start_utc = day_start_utc - timedelta(days=1)
        yesterday_end_utc = day_end_utc - timedelta(days=1)
        yesterday_transfer_kpis = AnalyticsDashboardRepository.fetch_transfer_kpis(
            session,
            day_start_utc=yesterday_start_utc,
            day_end_utc=yesterday_end_utc,
            month_start_utc=month_start_utc,
            now_utc=now,
        )
        sent_today = transfer_kpis["sent_today"]
        sent_yesterday = yesterday_transfer_kpis["sent_today"]
        if sent_yesterday > 0:
            sent_trend = round(((sent_today - sent_yesterday) / sent_yesterday) * 100.0, 1)
        elif sent_today > 0:
            sent_trend = 100.0
        else:
            sent_trend = 0.0

        trend_start_utc = (day_start_utc - timedelta(days=6))
        dispatch_orders = AnalyticsDashboardRepository.fetch_orders_for_dispatch_trend(
            session,
            trend_start_utc=trend_start_utc,
            trend_end_utc=now,
        )
        dispatch_map: dict[str, int] = {}
        for order in dispatch_orders:
            if order.dispatch_date is None:
                continue
            key = _local_date_key(order.dispatch_date, tz)
            dispatch_map[key] = dispatch_map.get(key, 0) + int(order.units or 0)
        daily_dispatch_trend = []
        for offset in range(6, -1, -1):
            day_key = (day_start_utc + timedelta(days=offset - 6))
            local_key = _local_date_key(day_key, tz)
            daily_dispatch_trend.append({"date": local_key, "value": float(dispatch_map.get(local_key, 0))})

        base_inventory, inventory_rows = AnalyticsDashboardRepository.fetch_batteries_for_inventory_trend(
            session,
            trend_start_utc=trend_start_utc,
            trend_end_utc=now,
        )
        inventory_additions: dict[str, int] = {}
        for battery in inventory_rows:
            key = _local_date_key(battery.created_at, tz)
            inventory_additions[key] = inventory_additions.get(key, 0) + 1
        running_inventory = int(base_inventory or 0)
        inventory_level_trend: list[dict[str, Any]] = []
        for offset in range(6, -1, -1):
            day_key = (day_start_utc + timedelta(days=offset - 6))
            local_key = _local_date_key(day_key, tz)
            running_inventory += inventory_additions.get(local_key, 0)
            inventory_level_trend.append({"date": local_key, "value": float(running_inventory)})

        stats = {
            "available_batteries": battery_kpis["available_batteries"],
            "deployed_batteries": battery_kpis["deployed_batteries"],
            "in_transit_batteries": battery_kpis["in_transit_batteries"],
            "pending_orders": pending_orders,
            "issue_count": battery_kpis["issue_count"],
            "total_batteries": battery_kpis["total_batteries"],
            "sent_today": sent_today,
            "sent_trend": sent_trend,
            "received_today": transfer_kpis["received_today"],
            "pending_receipts": transfer_kpis["pending_receipts"],
            "revenue": float(revenue),
            "monthly_dispatch": transfer_kpis["monthly_dispatch"],
        }
        analytics = {
            "battery_status_distribution": AnalyticsDashboardRepository.fetch_battery_status_distribution(session),
            "battery_health_distribution": AnalyticsDashboardRepository.fetch_battery_health_distribution(session),
            "cycle_count_distribution": AnalyticsDashboardRepository.fetch_cycle_count_distribution(session),
            "daily_dispatch_trend": daily_dispatch_trend,
            "inventory_level_trend": inventory_level_trend,
            "station_dispatch_distribution": AnalyticsDashboardRepository.fetch_station_dispatch_distribution(session),
        }
        return {"stats": stats, "analytics": analytics}

    @staticmethod
    def get_recent_activity(
        session: Session,
        *,
        skip: int = 0,
        limit: int = 20,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        timezone_name: str = "UTC",
        event_types_csv: Optional[str] = None,
        _cache_bypass: bool = False,
    ) -> dict[str, Any]:
        if skip < 0:
            raise HTTPException(status_code=400, detail="skip must be >= 0")
        if limit <= 0 or limit > 200:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 200")

        tz = resolve_timezone_or_400(timezone_name)
        from_utc = normalize_utc_naive(from_dt)
        to_utc = normalize_utc_naive(to_dt)
        if from_utc is None and to_utc is None:
            # Guard against full-table scans on high-cardinality activity sources.
            lookback_days = AnalyticsDashboardService._recent_activity_default_lookback_days()
            default_from = datetime.utcnow() - timedelta(days=lookback_days)
            from_utc = default_from.replace(hour=0, minute=0, second=0, microsecond=0)
        _ensure_valid_window(from_utc, to_utc)
        allowed_types = _parse_event_types_csv(event_types_csv)
        source_row_limit = AnalyticsDashboardService._recent_activity_source_row_budget(
            skip=skip,
            limit=limit,
        )

        if not _cache_bypass:
            cache_key = AnalyticsDashboardService._cache_key(
                AnalyticsDashboardService.RECENT_ACTIVITY_CACHE_NAMESPACE,
                {
                    "skip": skip,
                    "limit": limit,
                    "from_utc": from_utc.isoformat() if from_utc else None,
                    "to_utc": to_utc.isoformat() if to_utc else None,
                    "timezone": timezone_name,
                    "event_types": sorted(allowed_types) if allowed_types is not None else None,
                },
            )
            return AnalyticsDashboardService._cached_compute(
                cache_key=cache_key,
                ttl_seconds=AnalyticsDashboardService._recent_activity_cache_ttl_seconds(),
                compute=lambda: AnalyticsDashboardService.get_recent_activity(
                    session,
                    skip=skip,
                    limit=limit,
                    from_dt=from_utc,
                    to_dt=to_utc,
                    timezone_name=timezone_name,
                    event_types_csv=event_types_csv,
                    _cache_bypass=True,
                ),
            )

        events: list[_ActivityEvent] = []
        now_utc = datetime.utcnow()
        source_data_truncated = False

        orders = AnalyticsDashboardRepository.fetch_orders_for_activity(
            session,
            from_utc=from_utc,
            to_utc=to_utc,
            row_limit=source_row_limit,
        )
        if source_row_limit is not None and len(orders) >= source_row_limit:
            source_data_truncated = True
        for order in orders:
            order_ref = order.id
            if order.order_date and _is_in_window(order.order_date, from_utc=from_utc, to_utc=to_utc):
                events.append(
                    _ActivityEvent(
                        id=_event_id("order", order_ref, "created", order.order_date.isoformat()),
                        type="orderCreated",
                        title=f"Order {order_ref} created",
                        timestamp_utc=order.order_date,
                        reference_id=order_ref,
                        meta={"status": order.status, "units": order.units},
                    )
                )

            canonical_status = _canonical_order_status(order.status)
            if order.assigned_driver_id is not None and order.updated_at and _is_in_window(
                order.updated_at,
                from_utc=from_utc,
                to_utc=to_utc,
            ):
                events.append(
                    _ActivityEvent(
                        id=_event_id("order", order_ref, "driver_assigned", order.updated_at.isoformat()),
                        type="shipmentInTransit",
                        title=f"Driver assigned to order {order_ref}",
                        timestamp_utc=order.updated_at,
                        reference_id=order_ref,
                        meta={"driver_id": order.assigned_driver_id},
                    )
                )

            in_transit_timestamp = order.dispatch_date or order.updated_at
            if (
                in_transit_timestamp
                and (canonical_status == "in_transit" or order.dispatch_date is not None)
                and _is_in_window(in_transit_timestamp, from_utc=from_utc, to_utc=to_utc)
            ):
                events.append(
                    _ActivityEvent(
                        id=_event_id("order", order_ref, "in_transit", in_transit_timestamp.isoformat()),
                        type="shipmentInTransit",
                        title=f"Order {order_ref} is in transit",
                        timestamp_utc=in_transit_timestamp,
                        reference_id=order_ref,
                        meta={"status": order.status},
                    )
                )

            delivered_timestamp = order.delivered_at or (
                order.updated_at if canonical_status == "delivered" else None
            )
            if delivered_timestamp and _is_in_window(delivered_timestamp, from_utc=from_utc, to_utc=to_utc):
                if canonical_status == "delivered":
                    events.append(
                        _ActivityEvent(
                            id=_event_id("order", order_ref, "delivered", delivered_timestamp.isoformat()),
                            type="orderDelivered",
                            title=f"Order {order_ref} delivered",
                            timestamp_utc=delivered_timestamp,
                            reference_id=order_ref,
                            meta={"status": order.status},
                        )
                    )

        transfers = AnalyticsDashboardRepository.fetch_transfers_for_activity(
            session,
            from_utc=from_utc,
            to_utc=to_utc,
            row_limit=source_row_limit,
        )
        if source_row_limit is not None and len(transfers) >= source_row_limit:
            source_data_truncated = True
        for transfer in transfers:
            transfer_ref = f"TR-{transfer.id}"
            status_normalized = (transfer.status or "").strip().lower()
            created_ts = transfer.created_at
            if created_ts and _is_in_window(created_ts, from_utc=from_utc, to_utc=to_utc):
                events.append(
                    _ActivityEvent(
                        id=_event_id("transfer", transfer.id, "created", created_ts.isoformat()),
                        type="shipmentInTransit",
                        title=f"Transfer {transfer_ref} created",
                        timestamp_utc=created_ts,
                        reference_id=transfer_ref,
                        meta={
                            "status": transfer.status,
                            "from_location_type": transfer.from_location_type,
                            "from_location_id": transfer.from_location_id,
                            "to_location_type": transfer.to_location_type,
                            "to_location_id": transfer.to_location_id,
                        },
                    )
                )

            if status_normalized == "completed":
                completed_ts = transfer.completed_at or transfer.updated_at
                if completed_ts and _is_in_window(completed_ts, from_utc=from_utc, to_utc=to_utc):
                    events.append(
                        _ActivityEvent(
                            id=_event_id("transfer", transfer.id, "completed", completed_ts.isoformat()),
                            type="batteryReceived",
                            title=f"Transfer {transfer_ref} received",
                            timestamp_utc=completed_ts,
                            reference_id=transfer_ref,
                            meta={"status": transfer.status},
                        )
                    )
            elif status_normalized == "cancelled":
                cancelled_ts = transfer.updated_at
                if cancelled_ts and _is_in_window(cancelled_ts, from_utc=from_utc, to_utc=to_utc):
                    events.append(
                        _ActivityEvent(
                            id=_event_id("transfer", transfer.id, "cancelled", cancelled_ts.isoformat()),
                            type="inventoryAudit",
                            title=f"Transfer {transfer_ref} cancelled",
                            timestamp_utc=cancelled_ts,
                            reference_id=transfer_ref,
                            meta={"status": transfer.status},
                        )
                    )

        discrepancies = AnalyticsDashboardRepository.fetch_discrepancies_for_activity(
            session,
            from_utc=from_utc,
            to_utc=to_utc,
            row_limit=source_row_limit,
        )
        if source_row_limit is not None and len(discrepancies) >= source_row_limit:
            source_data_truncated = True
        for discrepancy in discrepancies:
            events.append(
                _ActivityEvent(
                    id=_event_id("audit", discrepancy.id, discrepancy.created_at.isoformat()),
                    type="inventoryAudit",
                    title=(
                        f"Inventory audit at {discrepancy.location_type} #{discrepancy.location_id} "
                        f"recorded ({discrepancy.status})"
                    ),
                    timestamp_utc=discrepancy.created_at,
                    reference_id=f"AUD-{discrepancy.id}",
                    meta={
                        "system_count": discrepancy.system_count,
                        "physical_count": discrepancy.physical_count,
                        "status": discrepancy.status,
                    },
                )
            )

        lifecycle_rows = AnalyticsDashboardRepository.fetch_battery_lifecycle_for_activity(
            session,
            from_utc=from_utc,
            to_utc=to_utc,
            row_limit=source_row_limit,
        )
        if source_row_limit is not None and len(lifecycle_rows) >= source_row_limit:
            source_data_truncated = True
        for lifecycle_event, battery in lifecycle_rows:
            mapped_type = _map_battery_lifecycle_event_type(lifecycle_event.event_type)
            if mapped_type is None:
                continue
            battery_ref = battery.serial_number if battery is not None else f"BAT-{lifecycle_event.battery_id}"
            title = f"Battery {battery_ref}: {(lifecycle_event.description or lifecycle_event.event_type or '').strip()}"
            if not title.strip():
                title = f"Battery {battery_ref}: {mapped_type}"
            events.append(
                _ActivityEvent(
                    id=_event_id("battery_evt", lifecycle_event.id, lifecycle_event.timestamp.isoformat()),
                    type=mapped_type,
                    title=title,
                    timestamp_utc=lifecycle_event.timestamp,
                    reference_id=battery_ref,
                    meta={
                        "event_type": lifecycle_event.event_type,
                        "actor_id": lifecycle_event.actor_id,
                    },
                )
            )

        table_events = AnalyticsDashboardRepository.fetch_activity_table_rows(
            session,
            from_utc=from_utc,
            to_utc=to_utc,
            row_limit=source_row_limit,
        )
        if source_row_limit is not None and len(table_events) >= source_row_limit:
            source_data_truncated = True
        for table_event in table_events:
            if table_event.event_type not in ALLOWED_ACTIVITY_EVENT_TYPES:
                continue
            meta: Optional[dict[str, Any]] = None
            if table_event.meta_json:
                try:
                    parsed = json.loads(table_event.meta_json)
                    if isinstance(parsed, dict):
                        meta = parsed
                except Exception:
                    meta = {"raw_meta": table_event.meta_json}
            events.append(
                _ActivityEvent(
                    id=table_event.id,
                    type=table_event.event_type,
                    title=table_event.title,
                    timestamp_utc=table_event.event_timestamp,
                    reference_id=table_event.reference_id,
                    meta=meta,
                )
            )

        if (from_utc is None or from_utc <= now_utc) and (to_utc is None or now_utc <= to_utc):
            for low_row in AnalyticsDashboardService._cached_low_inventory_counts(session):
                location_type = str(low_row["location_type"])
                location_id = int(low_row["location_id"])
                available_count = int(low_row["available_count"])
                threshold = int(low_row["threshold"])
                events.append(
                    _ActivityEvent(
                        id=_event_id("low_inventory", location_type, location_id, now_utc.isoformat()),
                        type="lowInventory",
                        title=f"Low inventory at {location_type} #{location_id}",
                        timestamp_utc=now_utc,
                        reference_id=f"{location_type.upper()}-{location_id}",
                        meta={
                            "location_type": location_type,
                            "location_id": location_id,
                            "available_count": available_count,
                            "threshold": threshold,
                        },
                    )
                )

        if allowed_types is not None:
            events = [event for event in events if event.type in allowed_types]

        events.sort(key=lambda item: (item.timestamp_utc, item.id), reverse=True)
        total = len(events)
        page = events[skip : skip + limit]
        has_more = (skip + len(page)) < total

        # For bounded source reads, preserve pagination semantics even when source data was capped.
        if source_row_limit is not None and source_data_truncated and not has_more and len(page) == limit:
            has_more = True
            total = max(total, skip + len(page) + 1)

        items = [
            {
                "id": event.id,
                "type": event.type,
                "title": event.title,
                "timestamp": _to_timezone(event.timestamp_utc, tz),
                "reference_id": event.reference_id,
                "meta": event.meta,
            }
            for event in page
        ]
        return {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": has_more,
        }

    @staticmethod
    def build_report_sections(
        session: Session,
        *,
        from_utc: datetime,
        to_utc: datetime,
        timezone_name: str,
        include_sections: Sequence[str],
    ) -> dict[str, Any]:
        tz = resolve_timezone_or_400(timezone_name)
        now_utc = to_utc if to_utc <= datetime.utcnow() else datetime.utcnow()
        dashboard_payload = AnalyticsDashboardService.build_dashboard_payload(
            session,
            timezone_name=timezone_name,
            now_utc=now_utc,
        )
        report_payload: dict[str, Any] = {
            "from": _to_timezone(from_utc, tz).isoformat(),
            "to": _to_timezone(to_utc, tz).isoformat(),
            "timezone": timezone_name,
        }

        include = set(include_sections)
        if "kpis" in include:
            report_payload["kpis"] = dashboard_payload["stats"]
        if "recent_activity" in include:
            page_size = 200
            collected_items: list[dict[str, Any]] = []
            cursor = 0
            total = 0
            while True:
                page = AnalyticsDashboardService.get_recent_activity(
                    session,
                    skip=cursor,
                    limit=page_size,
                    from_dt=from_utc,
                    to_dt=to_utc,
                    timezone_name=timezone_name,
                )
                total = int(page.get("total", total))
                items = list(page.get("items", []))
                if not items:
                    break
                collected_items.extend(items)
                if not page.get("has_more"):
                    break
                cursor += len(items)

            report_payload["recent_activity"] = {
                "items": collected_items,
                "total": total,
                "skip": 0,
                "limit": page_size,
                "has_more": False,
            }
        if "orders" in include:
            orders = AnalyticsDashboardRepository.fetch_orders_for_activity(
                session,
                from_utc=from_utc,
                to_utc=to_utc,
            )
            pipeline: dict[str, int] = {}
            for order in orders:
                canonical = _canonical_order_status(order.status) or "unknown"
                pipeline[canonical] = pipeline.get(canonical, 0) + 1
            report_payload["orders"] = {
                "total_orders": len(orders),
                "pipeline_split": pipeline,
            }
        if "inventory" in include:
            transfers = AnalyticsDashboardRepository.fetch_transfers_for_activity(
                session,
                from_utc=from_utc,
                to_utc=to_utc,
            )
            transfer_split: dict[str, int] = {}
            for transfer in transfers:
                key = (transfer.status or "unknown").strip().lower()
                transfer_split[key] = transfer_split.get(key, 0) + 1
            discrepancies = AnalyticsDashboardRepository.fetch_discrepancies_for_activity(
                session,
                from_utc=from_utc,
                to_utc=to_utc,
            )
            report_payload["inventory"] = {
                "transfer_split": transfer_split,
                "inventory_audit_count": len(discrepancies),
            }
        if "fleet" in include:
            lifecycle_events = AnalyticsDashboardRepository.fetch_battery_lifecycle_for_activity(
                session,
                from_utc=from_utc,
                to_utc=to_utc,
            )
            fault_or_maintenance = 0
            swaps = 0
            for event, _battery in lifecycle_events:
                mapped = _map_battery_lifecycle_event_type(event.event_type)
                if mapped == "batteryFault":
                    fault_or_maintenance += 1
                if mapped == "batterySwapped":
                    swaps += 1
            report_payload["fleet"] = {
                "battery_health_distribution": dashboard_payload["analytics"]["battery_health_distribution"],
                "issue_count": fault_or_maintenance,
                "battery_swapped_events": swaps,
            }

        report_payload["analytics"] = {
            "daily_dispatch_trend": dashboard_payload["analytics"]["daily_dispatch_trend"],
            "battery_health_distribution": dashboard_payload["analytics"]["battery_health_distribution"],
            "battery_status_distribution": dashboard_payload["analytics"]["battery_status_distribution"],
        }
        return report_payload


def map_battery_lifecycle_event_type(raw_event_type: Optional[str]) -> Optional[str]:
    """
    Thin wrapper exported for unit tests.
    """
    return _map_battery_lifecycle_event_type(raw_event_type)
