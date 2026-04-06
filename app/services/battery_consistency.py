from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.inventory import InventoryTransfer, InventoryTransferItem
from app.models.order import Order, OrderBattery
from app.models.station import Station
from app.models.warehouse import Rack, Shelf, ShelfBattery, Warehouse

_UNSET = object()

VALID_BATTERY_STATUSES = {
    "available",
    "deployed",
    "charging",
    "faulty",
    "maintenance",
    "reserved",
    "in_transit",
    "new",
    "ready",
    "retired",
}

VALID_LOCATION_TYPES = {"warehouse", "station", "customer", "transit", "shelf"}
LOCATION_TYPES_REQUIRING_ID = {"warehouse", "station", "shelf"}
LOCATION_TYPES_WITHOUT_ID = {"customer", "transit"}
TRANSFER_ELIGIBLE_STATION_STATUSES = {"active"}

ACTIVE_TRANSFER_STATUSES = {"pending", "in_transit"}
ACTIVE_ORDER_CANONICAL_STATUSES = {
    "pending",
    "in_transit",
}
ACTIVE_ORDER_STATUS_ALIASES = {
    "assigned",
    "new",
    "in_progress",
    "out_for_delivery",
    "dispatched",
}
ACTIVE_ORDER_NORMALIZED_STATUSES = ACTIVE_ORDER_CANONICAL_STATUSES | ACTIVE_ORDER_STATUS_ALIASES

TRANSIT_COMPATIBLE_STATUSES = {"in_transit", "deployed"}
ASSIGNABLE_TO_SHELF_STATUSES = {"available", "new", "ready", "charging", "maintenance"}


def transfer_eligible_warehouse_clause():
    """Shared warehouse-eligibility predicate for transfer workflows and listings."""
    return Warehouse.is_active == True  # noqa: E712


def _normalize_station_status(raw_status: Optional[str]) -> str:
    return str(raw_status or "").strip().lower().replace("-", "_").replace(" ", "_")


def is_station_transfer_eligible(station: Optional[Station]) -> bool:
    if station is None:
        return False
    if bool(getattr(station, "is_deleted", False)):
        return False
    return _normalize_station_status(getattr(station, "status", None)) in TRANSFER_ELIGIBLE_STATION_STATUSES


def get_transfer_eligible_warehouse(session: Session, warehouse_id: int) -> Optional[Warehouse]:
    return session.exec(
        select(Warehouse).where(
            Warehouse.id == warehouse_id,
            transfer_eligible_warehouse_clause(),
        )
    ).first()


def get_transfer_eligible_station(session: Session, station_id: int) -> Optional[Station]:
    station = session.get(Station, station_id)
    if not is_station_transfer_eligible(station):
        return None
    return station


def normalize_battery_serial(raw_serial: str, *, field_name: str = "battery_id") -> str:
    if not isinstance(raw_serial, str):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a string")

    serial = raw_serial.strip().upper()
    if not serial:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a non-empty string")
    return serial


def normalize_battery_serials(
    serials: Iterable[str],
    *,
    field_name: str,
    require_non_empty: bool = True,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for index, raw_serial in enumerate(serials):
        serial = normalize_battery_serial(raw_serial, field_name=f"{field_name}[{index}]")
        if serial in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate battery serial '{serial}' in {field_name}")
        seen.add(serial)
        normalized.append(serial)

    if require_non_empty and not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name} must not be empty")

    return normalized


def _get_shelf_assignment(
    session: Session,
    serial: str,
    *,
    for_update: bool = False,
) -> Optional[ShelfBattery]:
    query = select(ShelfBattery).where(func.upper(ShelfBattery.battery_id) == serial)
    if for_update:
        query = query.with_for_update()

    rows = session.exec(query).all()
    if len(rows) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Data integrity violation: multiple shelf assignments found for battery '{serial}' "
                "(case-insensitive match)"
            ),
        )
    return rows[0] if rows else None


def _fetch_batteries_case_insensitive(
    session: Session,
    serials: list[str],
    *,
    for_update: bool,
) -> list[Battery]:
    if not serials:
        return []

    query = (
        select(Battery)
        .where(func.upper(Battery.serial_number).in_(serials))
        .order_by(func.upper(Battery.serial_number).asc())
    )
    if for_update:
        query = query.with_for_update()

    rows = session.exec(query).all()
    by_serial: dict[str, Battery] = {}
    for row in rows:
        normalized = normalize_battery_serial(row.serial_number)
        if normalized in by_serial:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Data integrity violation: multiple battery rows found for serial '{normalized}' "
                    "(case-insensitive match)"
                ),
            )
        by_serial[normalized] = row

    missing = sorted(set(serials) - set(by_serial.keys()))
    if missing:
        raise HTTPException(status_code=400, detail=f"Batteries not found: {missing}")

    return [by_serial[serial] for serial in serials]


def get_battery_by_serial(
    session: Session,
    serial: str,
    *,
    for_update: bool = False,
) -> Optional[Battery]:
    normalized = normalize_battery_serial(serial)
    query = select(Battery).where(func.upper(Battery.serial_number) == normalized)
    if for_update:
        query = query.with_for_update()
    rows = session.exec(query).all()
    if len(rows) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Data integrity violation: multiple battery rows found for serial '{normalized}' "
                "(case-insensitive match)"
            ),
        )
    return rows[0] if rows else None


def fetch_batteries_by_serials(
    session: Session,
    serials: Iterable[str],
    *,
    field_name: str = "battery_ids",
    require_non_empty: bool = True,
    for_update: bool = False,
) -> list[Battery]:
    normalized = normalize_battery_serials(serials, field_name=field_name, require_non_empty=require_non_empty)
    return _fetch_batteries_case_insensitive(session, normalized, for_update=for_update)


def assert_location_exists(
    session: Session,
    *,
    location_type: Optional[str],
    location_id: Optional[int],
    location_role: str,
    require_transfer_eligibility: bool = False,
) -> None:
    if location_type is None:
        return

    if location_type not in VALID_LOCATION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {location_role}_location_type '{location_type}'. Allowed: {sorted(VALID_LOCATION_TYPES)}",
        )

    if location_type in LOCATION_TYPES_REQUIRING_ID:
        if location_id is None or location_id <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"{location_role}_location_id must be a positive integer when location_type is '{location_type}'",
            )

        if location_type == "warehouse":
            warehouse = get_transfer_eligible_warehouse(session, location_id)
            if not warehouse:
                raise HTTPException(
                    status_code=404,
                    detail=f"{location_role.capitalize()} warehouse #{location_id} not found or inactive",
                )
            return

        if location_type == "station":
            station = session.get(Station, location_id)
            if not station:
                raise HTTPException(
                    status_code=404,
                    detail=f"{location_role.capitalize()} station #{location_id} not found",
                )
            if bool(getattr(station, "is_deleted", False)):
                raise HTTPException(
                    status_code=404,
                    detail=f"{location_role.capitalize()} station #{location_id} not found or inactive",
                )
            if require_transfer_eligibility and not is_station_transfer_eligible(station):
                raise HTTPException(
                    status_code=404,
                    detail=f"{location_role.capitalize()} station #{location_id} not found or inactive",
                )
            return

        shelf_in_active_warehouse = session.exec(
            select(Shelf.id)
            .join(Rack, Rack.id == Shelf.rack_id)
            .join(Warehouse, Warehouse.id == Rack.warehouse_id)
            .where(Shelf.id == location_id, Warehouse.is_active == True)
        ).first()
        if not shelf_in_active_warehouse:
            shelf = session.get(Shelf, location_id)
            if shelf:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{location_role.capitalize()} shelf #{location_id} belongs to an inactive warehouse"
                    ),
                )
            raise HTTPException(
                status_code=404,
                detail=f"{location_role.capitalize()} shelf #{location_id} not found",
            )
        return

    if location_type in LOCATION_TYPES_WITHOUT_ID and location_id is not None:
        raise HTTPException(
            status_code=400,
            detail=f"{location_role}_location_id must be omitted when location_type is '{location_type}'",
        )


def resolve_intake_warehouse_id(
    session: Session,
    *,
    warehouse_id: Optional[int] = None,
) -> int:
    if warehouse_id is not None:
        warehouse = get_transfer_eligible_warehouse(session, warehouse_id)
        if not warehouse:
            raise HTTPException(status_code=404, detail=f"Warehouse #{warehouse_id} not found or inactive")
        return warehouse.id

    active_warehouses = session.exec(
        select(Warehouse.id).where(transfer_eligible_warehouse_clause()).order_by(Warehouse.id.asc())
    ).all()
    if not active_warehouses:
        raise HTTPException(status_code=404, detail="No active warehouse configured")
    if len(active_warehouses) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple active warehouses found. Provide warehouse_id explicitly.",
        )
    return active_warehouses[0]


def get_single_active_warehouse_id(session: Session) -> Optional[int]:
    active_ids = session.exec(
        select(Warehouse.id).where(transfer_eligible_warehouse_clause()).order_by(Warehouse.id.asc())
    ).all()
    if len(active_ids) == 1:
        return active_ids[0]
    return None


def assert_batteries_not_in_active_transfers(
    session: Session,
    serials: Iterable[str],
    *,
    exclude_transfer_id: Optional[int] = None,
) -> None:
    normalized = normalize_battery_serials(serials, field_name="battery_ids", require_non_empty=False)
    if not normalized:
        return

    query = (
        select(InventoryTransferItem.battery_id, InventoryTransfer.id)
        .join(InventoryTransfer, InventoryTransferItem.transfer_id == InventoryTransfer.id)
        .where(
            InventoryTransfer.status.in_(ACTIVE_TRANSFER_STATUSES),
            func.upper(InventoryTransferItem.battery_id).in_(normalized),
        )
    )
    if exclude_transfer_id is not None:
        query = query.where(InventoryTransfer.id != exclude_transfer_id)

    conflicts: dict[str, set[int]] = {}
    for battery_id, transfer_id in session.exec(query).all():
        normalized_battery_id = normalize_battery_serial(battery_id)
        conflicts.setdefault(normalized_battery_id, set()).add(transfer_id)

    if conflicts:
        conflict_payload = {
            serial: sorted(list(transfer_ids))
            for serial, transfer_ids in sorted(conflicts.items())
        }
        raise HTTPException(
            status_code=409,
            detail=f"Batteries already in active transfers: {conflict_payload}",
        )


def assert_batteries_not_in_active_orders(
    session: Session,
    serials: Iterable[str],
    *,
    exclude_order_id: Optional[str] = None,
) -> None:
    normalized = normalize_battery_serials(serials, field_name="battery_ids", require_non_empty=False)
    if not normalized:
        return

    normalized_order_status = func.replace(
        func.replace(func.lower(Order.status), "-", "_"),
        " ",
        "_",
    )

    query = (
        select(OrderBattery.battery_id, Order.id)
        .join(Order, OrderBattery.order_id == Order.id)
        .where(
            normalized_order_status.in_(ACTIVE_ORDER_NORMALIZED_STATUSES),
            func.upper(OrderBattery.battery_id).in_(normalized),
        )
    )
    if exclude_order_id:
        query = query.where(Order.id != exclude_order_id)

    conflicts: dict[str, set[str]] = {}
    for battery_id, order_id in session.exec(query).all():
        normalized_battery_id = normalize_battery_serial(battery_id)
        conflicts.setdefault(normalized_battery_id, set()).add(order_id)

    if conflicts:
        conflict_payload = {
            serial: sorted(list(order_ids))
            for serial, order_ids in sorted(conflicts.items())
        }
        raise HTTPException(
            status_code=409,
            detail=f"Batteries already assigned to active orders: {conflict_payload}",
        )


def assert_battery_not_locked(
    session: Session,
    serial: str,
    *,
    exclude_transfer_id: Optional[int] = None,
    exclude_order_id: Optional[str] = None,
    skip_active_transfer_check: bool = False,
    skip_active_order_check: bool = False,
) -> None:
    normalized = normalize_battery_serial(serial)

    if not skip_active_transfer_check:
        assert_batteries_not_in_active_transfers(
            session,
            [normalized],
            exclude_transfer_id=exclude_transfer_id,
        )

    if not skip_active_order_check:
        assert_batteries_not_in_active_orders(
            session,
            [normalized],
            exclude_order_id=exclude_order_id,
        )


def assert_battery_shelf_state_consistent(session: Session, battery: Battery) -> None:
    serial = normalize_battery_serial(battery.serial_number)
    assignment = _get_shelf_assignment(session, serial, for_update=False)

    if battery.location_type == "shelf":
        if battery.location_id is None:
            raise HTTPException(
                status_code=409,
                detail=f"Battery '{serial}' is at shelf location type but location_id is missing",
            )
        if not assignment:
            raise HTTPException(
                status_code=409,
                detail=f"Battery '{serial}' is shelf-located but has no shelf assignment row",
            )
        if assignment.shelf_id != battery.location_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Battery '{serial}' location points to shelf #{battery.location_id} "
                    f"but assignment row points to shelf #{assignment.shelf_id}"
                ),
            )
        return

    if assignment:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Battery '{serial}' has stale shelf assignment row for shelf #{assignment.shelf_id} "
                f"while location_type is '{battery.location_type}'"
            ),
        )


def apply_battery_transition(
    session: Session,
    *,
    battery: Battery,
    event_type: str,
    event_description: str,
    actor_id: Optional[int] = None,
    decommission_reason: Optional[str] = None,
    to_status: Optional[str] = None,
    to_location_type: Optional[str] = None,
    to_location_id: Optional[int] | object = _UNSET,
    exclude_transfer_id: Optional[int] = None,
    exclude_order_id: Optional[str] = None,
    skip_active_transfer_check: bool = False,
    skip_active_order_check: bool = False,
) -> None:
    serial = normalize_battery_serial(battery.serial_number)
    battery.serial_number = serial

    target_status = battery.status if to_status is None else to_status
    target_location_type = battery.location_type if to_location_type is None else to_location_type
    target_location_id = battery.location_id if to_location_id is _UNSET else to_location_id

    if target_status not in VALID_BATTERY_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid battery status '{target_status}'. Allowed: {sorted(VALID_BATTERY_STATUSES)}",
        )

    if battery.status == "retired" and target_status != "retired":
        raise HTTPException(
            status_code=409,
            detail=f"Battery '{serial}' is retired and cannot transition back to active states",
        )

    if target_location_type is not None:
        assert_location_exists(
            session,
            location_type=target_location_type,
            location_id=target_location_id,
            location_role="target",
        )

    if target_location_type == "transit" and target_status not in TRANSIT_COMPATIBLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "location_type 'transit' is only allowed with statuses "
                f"{sorted(TRANSIT_COMPATIBLE_STATUSES)}"
            ),
        )

    assert_battery_not_locked(
        session,
        serial,
        exclude_transfer_id=exclude_transfer_id,
        exclude_order_id=exclude_order_id,
        skip_active_transfer_check=skip_active_transfer_check,
        skip_active_order_check=skip_active_order_check,
    )

    assignment = _get_shelf_assignment(session, serial, for_update=True)

    if target_location_type == "shelf":
        if target_location_id is None:
            raise HTTPException(status_code=400, detail="target_location_id is required for shelf assignments")

        target_shelf = session.get(Shelf, target_location_id)
        if not target_shelf:
            raise HTTPException(status_code=404, detail=f"Shelf #{target_location_id} not found")

        if assignment and assignment.shelf_id == target_location_id:
            pass
        else:
            shelf_count = session.exec(
                select(func.count(ShelfBattery.id)).where(ShelfBattery.shelf_id == target_location_id)
            ).one()
            if shelf_count >= target_shelf.capacity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Shelf #{target_location_id} is at full capacity",
                )

            if assignment is not None:
                session.delete(assignment)
                session.flush()
            session.add(ShelfBattery(shelf_id=target_location_id, battery_id=serial))
    else:
        if assignment is not None:
            session.delete(assignment)
            session.flush()

    if target_location_type in LOCATION_TYPES_WITHOUT_ID:
        target_location_id = None

    battery.status = target_status
    battery.location_type = target_location_type
    battery.location_id = target_location_id
    battery.updated_at = datetime.utcnow()

    if target_status == "retired":
        now = datetime.utcnow()
        if battery.retirement_date is None:
            battery.retirement_date = now
        if battery.decommissioned_at is None:
            battery.decommissioned_at = now
        if actor_id is not None:
            battery.decommissioned_by = actor_id
        cleaned_reason = (decommission_reason or "").strip()
        if cleaned_reason:
            battery.decommission_reason = cleaned_reason

    session.add(battery)
    session.add(
        BatteryLifecycleEvent(
            battery_id=battery.id,
            event_type=event_type,
            description=event_description,
            actor_id=actor_id,
        )
    )
