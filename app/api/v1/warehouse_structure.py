from __future__ import annotations
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import load_only, selectinload
from sqlmodel import Session, select

from app.api import deps
from app.core.config import settings
from app.db.session import get_session
from app.models.battery import Battery
from app.models.user import User
from app.models.warehouse import Rack, Shelf, ShelfBattery, Warehouse
from app.schemas.warehouse_structure import (
    BatteryAssignRequest,
    RackResponse,
    ShelfDataResponse,
    ShelfResponse,
    WarehouseStructureListWrapper,
    WarehouseStructureResponse,
    WarehouseWrapper,
)
from app.services.redis_service import RedisService
from app.services.distributed_cache_service import DistributedCacheService
from app.services.battery_consistency import (
    ASSIGNABLE_TO_SHELF_STATUSES as SHELF_ASSIGNABLE_STATUSES,
    apply_battery_transition,
    get_battery_by_serial,
    normalize_battery_serial,
)
from app.services.idempotency_service import (
    build_request_fingerprint,
    get_idempotent_replay,
    normalize_idempotency_key,
    record_idempotent_response,
)

router = APIRouter()
logger = logging.getLogger(__name__)
WAREHOUSE_STRUCTURES_CACHE_NAMESPACE = "wezu:warehouse_structures:list:v1"


def _reference_cache_ttl_seconds() -> int:
    raw = int(getattr(settings, "REFERENCE_LIST_CACHE_TTL_SECONDS", 60) or 60)
    return max(30, min(120, raw))


def _reference_cache_ttl_jitter_seconds() -> int:
    raw = int(getattr(settings, "REFERENCE_LIST_CACHE_TTL_JITTER_SECONDS", 5) or 5)
    return max(0, min(30, raw))


def _reference_cache_stale_ttl_seconds() -> int:
    raw = int(getattr(settings, "REFERENCE_LIST_CACHE_STALE_TTL_SECONDS", 180) or 180)
    return max(30, min(900, raw))


def _reference_cache_lock_wait_ms() -> int:
    raw = int(getattr(settings, "REFERENCE_LIST_CACHE_LOCK_WAIT_MS", 800) or 800)
    return max(0, min(5000, raw))


def _reference_cache_lock_poll_ms() -> int:
    raw = int(getattr(settings, "REFERENCE_LIST_CACHE_LOCK_POLL_MS", 40) or 40)
    return max(10, min(500, raw))


def _reference_cache_lock_ttl_seconds() -> int:
    raw = int(getattr(settings, "ANALYTICS_CACHE_LOCK_TTL_SECONDS", 5) or 5)
    return max(1, min(30, raw))


def _warehouse_structures_cache_key(active_only: bool) -> str:
    return DistributedCacheService.build_key(
        WAREHOUSE_STRUCTURES_CACHE_NAMESPACE,
        {"active_only": bool(active_only)},
    )


def _invalidate_cached_warehouse_structures() -> None:
    client = RedisService.get_client()
    if client is None:
        return
    try:
        client.delete(
            _warehouse_structures_cache_key(True),
            _warehouse_structures_cache_key(False),
        )
    except Exception:
        logger.exception("Failed to invalidate cached warehouse structures")


def _build_structure_response(warehouse: Warehouse) -> WarehouseStructureResponse:
    racks_data = []
    for rack in warehouse.racks:
        shelves_data = []
        for shelf in rack.shelves:
            shelves_data.append(
                ShelfResponse(
                    id=shelf.id,
                    name=shelf.name,
                    capacity=shelf.capacity,
                    battery_ids=shelf.battery_ids,
                )
            )

        racks_data.append(
            RackResponse(
                id=rack.id,
                name=rack.name,
                shelves=shelves_data,
            )
        )

    return WarehouseStructureResponse(
        id=warehouse.id,
        name=warehouse.name,
        racks=racks_data,
    )


@router.get("/", response_model=WarehouseWrapper)
def get_warehouse_structure(
    warehouse_id: Optional[int] = None,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
):
    """
    Get warehouse structure (racks and shelves).
    If `warehouse_id` is not provided, falls back to the single active warehouse.
    """
    if warehouse_id is not None:
        warehouse = session.get(Warehouse, warehouse_id)
        if not warehouse:
            raise HTTPException(status_code=404, detail=f"Warehouse #{warehouse_id} not found")
        return WarehouseWrapper(success=True, data=_build_structure_response(warehouse))

    active_warehouses = session.exec(
        select(Warehouse).where(Warehouse.is_active == True).order_by(Warehouse.id.asc())
    ).all()
    if not active_warehouses:
        fallback = session.exec(select(Warehouse).order_by(Warehouse.id.asc())).first()
        if fallback:
            logger.warning(
                "No active warehouse configured; falling back to warehouse_id=%s",
                fallback.id,
            )
            return WarehouseWrapper(success=True, data=_build_structure_response(fallback))
        raise HTTPException(status_code=404, detail="No warehouse configured")
    if len(active_warehouses) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Multiple active warehouses found. Provide 'warehouse_id' query param "
                "or use '/warehouse/all' to list structures."
            ),
        )
    return WarehouseWrapper(success=True, data=_build_structure_response(active_warehouses[0]))


@router.get("/all", response_model=WarehouseStructureListWrapper)
def list_warehouse_structures(
    active_only: bool = True,
    response: Response = None,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
):
    """
    List structures for all warehouses.
    """
    def _compute_payload() -> list[dict]:
        query = select(Warehouse).order_by(Warehouse.id.asc())
        query = query.options(
            load_only(Warehouse.id, Warehouse.name, Warehouse.is_active),
            selectinload(Warehouse.racks)
            .options(load_only(Rack.id, Rack.name, Rack.warehouse_id))
            .selectinload(Rack.shelves)
            .options(load_only(Shelf.id, Shelf.name, Shelf.capacity, Shelf.rack_id))
            .selectinload(Shelf.shelf_batteries)
            .options(load_only(ShelfBattery.battery_id, ShelfBattery.shelf_id)),
        )
        if active_only:
            query = query.where(Warehouse.is_active == True)
        warehouses: List[Warehouse] = session.exec(query).all()
        structures = [_build_structure_response(warehouse) for warehouse in warehouses]
        return [item.model_dump(mode="json") for item in structures]

    cache_result = DistributedCacheService.get_or_compute_json(
        cache_key=_warehouse_structures_cache_key(active_only),
        ttl_seconds=_reference_cache_ttl_seconds(),
        compute=_compute_payload,
        lock_ttl_seconds=_reference_cache_lock_ttl_seconds(),
        lock_wait_ms=_reference_cache_lock_wait_ms(),
        lock_poll_ms=_reference_cache_lock_poll_ms(),
        ttl_jitter_seconds=_reference_cache_ttl_jitter_seconds(),
        stale_ttl_seconds=_reference_cache_stale_ttl_seconds(),
        allow_stale_on_error=True,
        log_label="warehouse_structures",
    )
    if response is not None and settings.DEBUG:
        response.headers["X-Cache-Warehouse-Structures"] = cache_result.source
    payload = cache_result.payload if isinstance(cache_result.payload, list) else []
    structures = [WarehouseStructureResponse.model_validate(item) for item in payload if isinstance(item, dict)]
    return WarehouseStructureListWrapper(success=True, data=structures)


@router.post("/shelves/{shelf_id}/batteries", response_model=ShelfDataResponse)
def assign_battery_to_shelf(
    shelf_id: int,
    body: BatteryAssignRequest,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """
    Assign a battery serial to a specific shelf.
    If already on another shelf in the same warehouse, it is moved atomically.
    """
    shelf = session.exec(
        select(Shelf).where(Shelf.id == shelf_id).with_for_update()
    ).first()
    if not shelf:
        raise HTTPException(status_code=404, detail="Shelf not found")

    target_warehouse_id = session.exec(
        select(Rack.warehouse_id).where(Rack.id == shelf.rack_id)
    ).first()
    if target_warehouse_id is None:
        raise HTTPException(status_code=409, detail=f"Shelf #{shelf_id} rack linkage is invalid")

    target_warehouse = session.get(Warehouse, target_warehouse_id)
    if not target_warehouse or not target_warehouse.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Target warehouse #{target_warehouse_id} is not active",
        )

    serial = normalize_battery_serial(body.battery_id, field_name="battery_id")
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/warehouse/shelves/{shelf_id}/batteries"
    request_fingerprint = build_request_fingerprint(
        {"shelf_id": shelf_id, "battery_id": serial}
    )
    replay_payload = get_idempotent_replay(
        session,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method="POST",
        request_path=request_path,
        request_fingerprint=request_fingerprint,
    )
    if replay_payload is not None:
        return ShelfDataResponse(**replay_payload)

    battery = get_battery_by_serial(session, serial, for_update=True)
    if not battery:
        raise HTTPException(status_code=404, detail=f"Battery '{serial}' not found")
    if battery.status not in SHELF_ASSIGNABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Battery '{serial}' is '{battery.status}' and cannot be assigned to shelf. "
                f"Allowed statuses: {sorted(SHELF_ASSIGNABLE_STATUSES)}"
            ),
        )

    if battery.location_type == "warehouse":
        if battery.location_id != target_warehouse_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Battery '{serial}' is at warehouse #{battery.location_id}, "
                    f"cannot assign to shelf in warehouse #{target_warehouse_id}"
                ),
            )
    elif battery.location_type == "shelf":
        source_warehouse_id = session.exec(
            select(Rack.warehouse_id)
            .join(Shelf, Shelf.rack_id == Rack.id)
            .where(Shelf.id == battery.location_id)
        ).first()
        if source_warehouse_id != target_warehouse_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Battery '{serial}' is on a shelf in warehouse #{source_warehouse_id}. "
                    f"Cross-warehouse shelf moves require an inventory transfer first."
                ),
            )
        if battery.location_id == shelf_id:
            raise HTTPException(status_code=400, detail="Battery already on this shelf")
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Battery '{serial}' at location '{battery.location_type}' cannot be assigned to shelf. "
                "Move it to the target warehouse first."
            ),
        )

    try:
        apply_battery_transition(
            session,
            battery=battery,
            to_status=battery.status,
            to_location_type="shelf",
            to_location_id=shelf.id,
            event_type="shelf_assigned",
            event_description=f"Assigned to shelf {shelf.name} (id={shelf.id})",
            actor_id=current_user.id,
        )
        session.flush()
        session.refresh(shelf)

        response = ShelfDataResponse(
            success=True,
            data=ShelfResponse(
                id=shelf.id,
                name=shelf.name,
                capacity=shelf.capacity,
                battery_ids=shelf.battery_ids,
            ),
        )
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
        _invalidate_cached_warehouse_structures()
        return response
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Concurrent shelf assignment conflict detected. Please retry.",
        ) from exc
