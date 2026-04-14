from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.models.battery import Battery
from app.models.driver_profile import DriverProfile
from app.models.inventory import InventoryTransfer
from app.models.order import Order
from app.models.station import Station
from app.models.warehouse import Warehouse
from app.services.analytics_dashboard_service import AnalyticsDashboardService
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


def _as_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


class BootstrapService:
    WAREHOUSES_CACHE_KEY = "wezu:bootstrap:refs:warehouses:active:v1"
    STATIONS_CACHE_KEY = "wezu:bootstrap:refs:stations:active:v1"

    @staticmethod
    def _ref_cache_ttl_seconds() -> int:
        raw = int(getattr(settings, "REFERENCE_LIST_CACHE_TTL_SECONDS", 60) or 60)
        return max(30, min(120, raw))

    @staticmethod
    def _cache_get_list(cache_key: str) -> list[dict[str, Any]] | None:
        client = RedisService.get_client()
        if client is None:
            return None
        try:
            cached = client.get(cache_key)
            if not cached:
                return None
            parsed = json.loads(cached)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
        except Exception:
            logger.exception("Bootstrap cache read failed key=%s", cache_key)
        return None

    @staticmethod
    def _cache_set_list(cache_key: str, payload: list[dict[str, Any]]) -> None:
        client = RedisService.get_client()
        if client is None:
            return
        try:
            client.setex(
                cache_key,
                BootstrapService._ref_cache_ttl_seconds(),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception:
            logger.exception("Bootstrap cache write failed key=%s", cache_key)

    @staticmethod
    def active_warehouse_refs(session: Session) -> list[dict[str, Any]]:
        cached = BootstrapService._cache_get_list(BootstrapService.WAREHOUSES_CACHE_KEY)
        if cached is not None:
            return cached

        rows = session.exec(
            select(Warehouse)
            .where(Warehouse.is_active == True)
            .order_by(Warehouse.id.asc())
        ).all()
        payload: list[dict[str, Any]] = []
        for row in rows:
            if row.id is None:
                continue
            payload.append(
                {
                    "id": int(row.id),
                    "name": row.name,
                    "code": row.code,
                    "city": row.city,
                    "state": row.state,
                    "is_active": bool(row.is_active),
                }
            )
        BootstrapService._cache_set_list(BootstrapService.WAREHOUSES_CACHE_KEY, payload)
        return payload

    @staticmethod
    def active_station_refs(session: Session) -> list[dict[str, Any]]:
        cached = BootstrapService._cache_get_list(BootstrapService.STATIONS_CACHE_KEY)
        if cached is not None:
            return cached

        rows = session.exec(
            select(Station)
            .where(
                Station.is_deleted == False,  # noqa: E712
                Station.status == "active",
            )
            .order_by(Station.id.asc())
        ).all()
        payload: list[dict[str, Any]] = []
        for row in rows:
            if row.id is None:
                continue
            payload.append(
                {
                    "id": int(row.id),
                    "name": row.name,
                    "status": row.status,
                    "address": row.address,
                    "latitude": float(row.latitude),
                    "longitude": float(row.longitude),
                }
            )
        BootstrapService._cache_set_list(BootstrapService.STATIONS_CACHE_KEY, payload)
        return payload

    @staticmethod
    def _paginated(items: list[dict[str, Any]], *, total: int, skip: int, limit: int) -> dict[str, Any]:
        return {
            "items": items,
            "total": int(total),
            "skip": int(skip),
            "limit": int(limit),
            "has_more": (skip + len(items)) < int(total),
        }

    @staticmethod
    def build_first_screen_payload(
        session: Session,
        *,
        timezone_name: str = "UTC",
        skip: int = 0,
        orders_limit: int = 20,
        transfers_limit: int = 20,
        drivers_limit: int = 20,
        batteries_limit: int = 50,
        include_heavy_panels: bool = False,
    ) -> dict[str, Any]:
        if skip < 0:
            raise ValueError("skip must be >= 0")

        dashboard_payload = AnalyticsDashboardService.build_dashboard_payload(
            session,
            timezone_name=timezone_name,
        )
        recent_activity = AnalyticsDashboardService.get_recent_activity(
            session,
            skip=skip,
            limit=20,
            timezone_name=timezone_name,
        )

        if include_heavy_panels:
            dashboard = dashboard_payload
        else:
            analytics = dashboard_payload.get("analytics") if isinstance(dashboard_payload, dict) else {}
            dashboard = {
                "stats": dashboard_payload.get("stats", {}) if isinstance(dashboard_payload, dict) else {},
                "analytics": {
                    "battery_status_distribution": (
                        analytics.get("battery_status_distribution", []) if isinstance(analytics, dict) else []
                    ),
                    "battery_health_distribution": (
                        analytics.get("battery_health_distribution", []) if isinstance(analytics, dict) else []
                    ),
                },
            }

        orders_total = int(session.exec(select(func.count(Order.id))).one() or 0)
        orders_rows = session.exec(
            select(Order)
            .order_by(Order.order_date.desc(), Order.updated_at.desc())
            .offset(skip)
            .limit(orders_limit)
        ).all()
        orders_items = [
            {
                "id": order.id,
                "status": order.status,
                "priority": order.priority,
                "destination": order.destination,
                "customer_name": order.customer_name,
                "units": int(order.units or 0),
                "order_date": _as_iso(order.order_date),
                "updated_at": _as_iso(order.updated_at),
                "assigned_driver_id": int(order.assigned_driver_id) if order.assigned_driver_id is not None else None,
            }
            for order in orders_rows
        ]

        transfers_total = int(session.exec(select(func.count(InventoryTransfer.id))).one() or 0)
        transfer_rows = session.exec(
            select(InventoryTransfer)
            .order_by(InventoryTransfer.created_at.desc(), InventoryTransfer.id.desc())
            .offset(skip)
            .limit(transfers_limit)
        ).all()
        transfer_items = [
            {
                "id": int(transfer.id),
                "status": transfer.status,
                "from_location_type": transfer.from_location_type,
                "from_location_id": int(transfer.from_location_id),
                "to_location_type": transfer.to_location_type,
                "to_location_id": int(transfer.to_location_id),
                "driver_id": int(transfer.driver_id) if transfer.driver_id is not None else None,
                "created_at": _as_iso(transfer.created_at),
                "updated_at": _as_iso(transfer.updated_at),
            }
            for transfer in transfer_rows
        ]

        drivers_total = int(session.exec(select(func.count(DriverProfile.id))).one() or 0)
        driver_rows = session.exec(
            select(DriverProfile)
            .order_by(DriverProfile.created_at.desc(), DriverProfile.id.desc())
            .offset(skip)
            .limit(drivers_limit)
        ).all()
        driver_items = [
            {
                "id": int(driver.id),
                "code": f"D-{driver.id}",
                "name": driver.name,
                "status": driver.status,
                "is_online": bool(driver.is_online),
                "vehicle_type": driver.vehicle_type,
                "vehicle_plate": driver.vehicle_plate,
                "updated_at": _as_iso(driver.last_location_update or driver.created_at),
            }
            for driver in driver_rows
            if driver.id is not None
        ]

        batteries_total = int(session.exec(select(func.count(Battery.id))).one() or 0)
        battery_rows = session.exec(
            select(Battery)
            .order_by(Battery.updated_at.desc(), Battery.id.desc())
            .offset(skip)
            .limit(batteries_limit)
        ).all()
        battery_items = [
            {
                "id": int(battery.id),
                "serial_number": battery.serial_number,
                "status": battery.status,
                "location_type": battery.location_type,
                "location_id": int(battery.location_id) if battery.location_id is not None else None,
                "health_percentage": int(battery.health_percentage or 0),
                "cycle_count": int(battery.cycle_count or 0),
                "updated_at": _as_iso(battery.updated_at),
            }
            for battery in battery_rows
            if battery.id is not None
        ]

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "health_probe_url": "/health",
            "defer_ready_endpoint_for_boot": True,
            "dashboard": dashboard,
            "recent_activity": recent_activity,
            "references": {
                "cache_ttl_seconds": BootstrapService._ref_cache_ttl_seconds(),
                "warehouses": BootstrapService.active_warehouse_refs(session),
                "stations": BootstrapService.active_station_refs(session),
            },
            "lists": {
                "orders": BootstrapService._paginated(
                    orders_items,
                    total=orders_total,
                    skip=skip,
                    limit=orders_limit,
                ),
                "transfers": BootstrapService._paginated(
                    transfer_items,
                    total=transfers_total,
                    skip=skip,
                    limit=transfers_limit,
                ),
                "drivers": BootstrapService._paginated(
                    driver_items,
                    total=drivers_total,
                    skip=skip,
                    limit=drivers_limit,
                ),
                "batteries": BootstrapService._paginated(
                    battery_items,
                    total=batteries_total,
                    skip=skip,
                    limit=batteries_limit,
                ),
            },
            "deferred_panels": [
                "/api/v1/analytics/dashboard?timezone=UTC",
                "/api/v1/analytics/recent-activity?skip=0&limit=50",
                "/api/v1/orders?skip=0&limit=100&include_pagination=true",
                "/api/v1/inventory/transfers?skip=0&limit=100&include_pagination=true",
            ],
        }
