from __future__ import annotations

import re
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.api import deps
from app.db.session import get_session
from app.models.battery import Battery, BatteryLifecycleEvent
from app.models.manifest import Manifest, ManifestItem
from app.models.user import User
from app.schemas.common import DataResponse
from app.schemas.manifest import ManifestCreate, ManifestRead, ManifestReceiveRequest
from app.services.battery_consistency import (
    apply_battery_transition,
    get_battery_by_serial,
    normalize_battery_serial,
    normalize_battery_serials,
    resolve_intake_warehouse_id,
)
from app.services.idempotency_service import (
    build_request_fingerprint,
    get_idempotent_replay,
    normalize_idempotency_key,
    record_idempotent_response,
)
from app.services.qr_service import BatteryQRCodeService

router = APIRouter()

ALLOWED_MANIFEST_ITEM_STATUSES = {"pending", "scanned", "missing", "damaged", "extra"}
ALLOWED_MANIFEST_STATUSES = {"In Transit", "In Progress", "Received", "Processed"}
INITIAL_MANIFEST_STATUSES = {"In Transit", "In Progress"}
RECEIVE_ALLOWED_MANIFEST_STATUSES = {"In Transit", "In Progress", "Received"}
MANIFEST_STATUS_CANONICAL_MAP = {
    "IN TRANSIT": "In Transit",
    "IN PROGRESS": "In Progress",
    "RECEIVED": "Received",
    "PROCESSED": "Processed",
}
MANIFEST_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._:-]{0,127}$")

def _normalize_manifest_id(raw_manifest_id: str, *, field_name: str = "manifest_id") -> str:
    if not isinstance(raw_manifest_id, str):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a string")

    manifest_id = raw_manifest_id.strip().upper()
    if not manifest_id:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a non-empty string")
    if not MANIFEST_ID_PATTERN.fullmatch(manifest_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{field_name} '{manifest_id}' has invalid format. "
                "Allowed: uppercase letters, digits, '.', '_', ':', '-'"
            ),
        )
    return manifest_id


def _normalize_manifest_source(raw_source: str) -> str:
    if not isinstance(raw_source, str):
        raise HTTPException(status_code=400, detail="Manifest source must be a string")
    source = raw_source.strip()
    if not source:
        raise HTTPException(status_code=400, detail="Manifest source is required")
    if len(source) > 255:
        raise HTTPException(status_code=400, detail="Manifest source must be at most 255 characters")
    return source


def _normalize_manifest_status(raw_status: str, *, field_name: str = "status") -> str:
    if not isinstance(raw_status, str):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a string")

    normalized = " ".join(raw_status.strip().replace("_", " ").replace("-", " ").upper().split())
    status = MANIFEST_STATUS_CANONICAL_MAP.get(normalized)
    if not status:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} '{raw_status}'. Allowed: {sorted(ALLOWED_MANIFEST_STATUSES)}",
        )
    return status


def _normalize_manifest_item_status(
    raw_status: str,
    *,
    field_name: str,
    allow_extra: bool = True,
) -> str:
    if not isinstance(raw_status, str):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a string")

    status = raw_status.strip().lower()
    if status not in ALLOWED_MANIFEST_ITEM_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} '{raw_status}'. Allowed: {sorted(ALLOWED_MANIFEST_ITEM_STATUSES)}",
        )
    if not allow_extra and status == "extra":
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} cannot be 'extra' at manifest creation time",
        )
    return status


def _normalize_manifest_item_type(raw_type: str, *, field_name: str) -> str:
    if not isinstance(raw_type, str):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a string")
    cleaned = raw_type.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    if len(cleaned) > 120:
        raise HTTPException(status_code=400, detail=f"{field_name} must be at most 120 characters")
    return cleaned


def _validate_manifest_list_query_params(
    *,
    skip: int,
    limit: int,
) -> None:
    if skip < 0:
        raise HTTPException(status_code=400, detail="skip must be >= 0")
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")


def _find_manifests_by_normalized_id(
    session: Session,
    normalized_manifest_id: str,
    *,
    for_update: bool = False,
) -> list[Manifest]:
    query = (
        select(Manifest)
        .where(func.upper(Manifest.id) == normalized_manifest_id)
        .options(selectinload(Manifest.items))
    )
    if for_update:
        query = query.with_for_update()
    return session.exec(query).all()


def _load_manifest_by_id(
    session: Session,
    normalized_manifest_id: str,
    *,
    for_update: bool = False,
) -> Manifest:
    rows = _find_manifests_by_normalized_id(
        session,
        normalized_manifest_id,
        for_update=for_update,
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Manifest '{normalized_manifest_id}' not found")
    if len(rows) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Data integrity violation: multiple manifests found for id '{normalized_manifest_id}' "
                "(case-insensitive match)"
            ),
        )
    return rows[0]


def _assert_unique_manifest_item_updates(receive_data: ManifestReceiveRequest) -> list[str]:
    if not receive_data.items:
        raise HTTPException(status_code=400, detail="At least one manifest item update is required")

    return normalize_battery_serials(
        [item.battery_id for item in receive_data.items],
        field_name="items.battery_id",
    )


def _build_manifest_item_map(items: Sequence[ManifestItem]) -> dict[str, ManifestItem]:
    item_map: dict[str, ManifestItem] = {}
    for item in items:
        serial = normalize_battery_serial(item.battery_id, field_name="manifest.items[].battery_id")
        existing = item_map.get(serial)
        if existing is not None and existing.id != item.id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Data integrity violation: manifest contains duplicate item rows "
                    f"for battery '{serial}'"
                ),
            )
        item_map[serial] = item
    return item_map


def _compute_manifest_status(items: Sequence[ManifestItem]) -> str:
    statuses = {item.status for item in items}
    if not statuses:
        return "In Transit"
    if "pending" in statuses or "missing" in statuses:
        return "In Progress"
    return "Received"


def _assert_manifest_receivable(manifest: Manifest) -> None:
    current_status = _normalize_manifest_status(manifest.status, field_name="manifest.status")
    manifest.status = current_status
    if current_status == "Processed":
        raise HTTPException(
            status_code=409,
            detail=f"Manifest '{manifest.id}' is Processed and cannot be modified via receive flow",
        )
    if current_status not in RECEIVE_ALLOWED_MANIFEST_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Manifest '{manifest.id}' status '{current_status}' cannot enter receive flow. "
                f"Allowed: {sorted(RECEIVE_ALLOWED_MANIFEST_STATUSES)}"
            ),
        )


def _resolve_receive_warehouse_id(session: Session, warehouse_id: Optional[int]) -> int:
    return resolve_intake_warehouse_id(session, warehouse_id=warehouse_id)


def _get_or_create_battery(
    session: Session,
    serial_number: str,
    *,
    warehouse_id: int,
    actor_id: int,
) -> Battery:
    normalized_serial = normalize_battery_serial(serial_number, field_name="battery_id")
    battery = get_battery_by_serial(session, normalized_serial, for_update=True)
    if battery:
        battery.serial_number = normalized_serial
        BatteryQRCodeService.ensure_battery_qr_identity(battery)
        return battery

    battery = Battery(
        serial_number=normalized_serial,
        status="available",
        location_type="warehouse",
        location_id=warehouse_id,
    )
    session.add(battery)
    session.flush()
    BatteryQRCodeService.ensure_battery_qr_identity(battery)
    session.add(
        # Creation event is tracked from day one for accountability.
        BatteryLifecycleEvent(
            battery_id=battery.id,
            event_type="created",
            description=f"Created from manifest processing at warehouse #{warehouse_id}",
            actor_id=actor_id,
        )
    )
    return battery

@router.get("/", response_model=DataResponse[List[ManifestRead]])
def get_manifests(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
):
    """
    List all manifests.
    """
    _validate_manifest_list_query_params(skip=skip, limit=limit)

    query = select(Manifest).options(selectinload(Manifest.items))
    if status:
        normalized_status = _normalize_manifest_status(status, field_name="status")
        query = query.where(Manifest.status == normalized_status)

    manifests = session.exec(query.order_by(Manifest.date.desc()).offset(skip).limit(limit)).all()
    return DataResponse(success=True, data=manifests)


@router.post("/", response_model=DataResponse[ManifestRead])
def create_manifest(
    manifest_data: ManifestCreate,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """
    Create a new manifest with items.
    """
    normalized_manifest_id = _normalize_manifest_id(manifest_data.id, field_name="id")
    source = _normalize_manifest_source(manifest_data.source)
    manifest_status = _normalize_manifest_status(manifest_data.status)
    if manifest_status not in INITIAL_MANIFEST_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Manifest can only be created as one of {sorted(INITIAL_MANIFEST_STATUSES)}. "
                f"Received '{manifest_status}'"
            ),
        )
    if not manifest_data.items:
        raise HTTPException(status_code=400, detail="Manifest must include at least one item")

    normalized_item_ids = normalize_battery_serials(
        [item.battery_id for item in manifest_data.items],
        field_name="items.battery_id",
    )

    item_payloads: list[dict] = []
    for idx, item_data in enumerate(manifest_data.items):
        item_status = _normalize_manifest_item_status(
            item_data.status,
            field_name=f"items[{idx}].status",
            allow_extra=False,
        )
        item_type = _normalize_manifest_item_type(
            item_data.type,
            field_name=f"items[{idx}].type",
        )
        item_payloads.append(
            {
                "battery_id": normalized_item_ids[idx],
                "type": item_type,
                "status": item_status,
            }
        )

    # If any non-pending state is supplied at creation, the manifest starts as In Progress.
    if manifest_status == "In Transit" and any(item["status"] != "pending" for item in item_payloads):
        manifest_status = "In Progress"

    payload = {
        "id": normalized_manifest_id,
        "source": source,
        "date": manifest_data.date.isoformat(),
        "status": manifest_status,
        "items": item_payloads,
    }
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_fingerprint = build_request_fingerprint(payload)
    request_path = "/manifests"
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

    if _find_manifests_by_normalized_id(session, normalized_manifest_id):
        raise HTTPException(
            status_code=409,
            detail=f"Manifest ID '{normalized_manifest_id}' already exists (case-insensitive match)",
        )

    manifest = Manifest(
        id=normalized_manifest_id,
        source=source,
        date=manifest_data.date,
        status=manifest_status,
    )
    session.add(manifest)

    for item in item_payloads:
        known_battery = get_battery_by_serial(session, item["battery_id"])
        battery_table_id = known_battery.id if known_battery else None

        session.add(
            ManifestItem(
                manifest_id=manifest.id,
                battery_id=item["battery_id"],
                serial_number=item["battery_id"],
                battery_table_id=battery_table_id,
                type=item["type"],
                status=item["status"],
            )
        )

    session.flush()

    manifest = _load_manifest_by_id(session, normalized_manifest_id)
    response = DataResponse(success=True, data=manifest)
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


@router.get("/{manifest_id}", response_model=DataResponse[ManifestRead])
def get_manifest(
    manifest_id: str,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
):
    """
    Get manifest by ID.
    """
    normalized_manifest_id = _normalize_manifest_id(manifest_id, field_name="manifest_id")
    manifest = _load_manifest_by_id(session, normalized_manifest_id)
    return DataResponse(success=True, data=manifest)


@router.post("/{manifest_id}/receive", response_model=DataResponse[ManifestRead])
def receive_manifest(
    manifest_id: str,
    receive_data: ManifestReceiveRequest,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """
    Process received stock: update manifest items, capture damages, and update battery state.
    """
    normalized_manifest_id = _normalize_manifest_id(manifest_id, field_name="manifest_id")
    normalized_update_ids = _assert_unique_manifest_item_updates(receive_data)
    receiving_warehouse_id = _resolve_receive_warehouse_id(session, receive_data.warehouse_id)

    normalized_updates: list[dict] = []
    for idx, item_update in enumerate(receive_data.items):
        normalized_updates.append(
            {
                "battery_id": normalized_update_ids[idx],
                "status": _normalize_manifest_item_status(
                    item_update.status,
                    field_name=f"items[{idx}].status",
                ),
                "damage_report": (item_update.damage_report or "").strip() or None,
                "damage_photo_path": (item_update.damage_photo_path or "").strip() or None,
            }
        )

    payload = {
        "manifest_id": normalized_manifest_id,
        "warehouse_id": receiving_warehouse_id,
        "items": normalized_updates,
    }
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/manifests/{normalized_manifest_id}/receive"
    request_fingerprint = build_request_fingerprint(payload)
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

    manifest = _load_manifest_by_id(session, normalized_manifest_id, for_update=True)
    _assert_manifest_receivable(manifest)

    item_map = _build_manifest_item_map(manifest.items)
    known_at_start = set(item_map.keys())

    for item_update in normalized_updates:
        battery_serial = item_update["battery_id"]
        item_status = item_update["status"]

        existing_item = item_map.get(battery_serial)
        if not existing_item:
            if item_status != "extra":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Battery '{battery_serial}' is not part of manifest '{manifest.id}'. "
                        f"Unknown items can only be submitted as status 'extra'."
                    ),
                )
            existing_item = ManifestItem(
                manifest_id=manifest.id,
                battery_id=battery_serial,
                serial_number=battery_serial,
                type="Unknown",
                status=item_status,
            )
            session.add(existing_item)
            session.flush()
            item_map[battery_serial] = existing_item
        else:
            if item_status == "extra" and battery_serial in known_at_start and existing_item.status != "extra":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Battery '{battery_serial}' already exists in manifest '{manifest.id}'. "
                        "Use statuses scanned/damaged/missing/pending for listed items."
                    ),
                )
            existing_item.battery_id = battery_serial
            existing_item.serial_number = battery_serial

        battery: Optional[Battery] = None
        if item_status in {"scanned", "damaged", "extra"}:
            battery = _get_or_create_battery(
                session,
                battery_serial,
                warehouse_id=receiving_warehouse_id,
                actor_id=current_user.id,
            )
            existing_item.battery_table_id = battery.id
        elif existing_item.battery_table_id is not None:
            battery = session.get(Battery, existing_item.battery_table_id)

        if item_status == "scanned":
            if battery is None:
                raise HTTPException(status_code=409, detail=f"Unable to resolve battery '{battery_serial}'")
            apply_battery_transition(
                session,
                battery=battery,
                to_status="available",
                to_location_type="warehouse",
                to_location_id=receiving_warehouse_id,
                event_type="manifest_scanned",
                event_description=f"Received via manifest {manifest.id}",
                actor_id=current_user.id,
            )
            existing_item.status = "scanned"
        elif item_status == "damaged":
            if battery is None:
                raise HTTPException(status_code=409, detail=f"Unable to resolve battery '{battery_serial}'")
            apply_battery_transition(
                session,
                battery=battery,
                to_status="maintenance",
                to_location_type="warehouse",
                to_location_id=receiving_warehouse_id,
                event_type="damage_report",
                event_description=(
                    f"Damage report via manifest {manifest.id}: {item_update['damage_report'] or 'Not provided'} "
                    f"| Photo: {item_update['damage_photo_path'] or 'None'}"
                ),
                actor_id=current_user.id,
            )
            existing_item.status = "damaged"
        elif item_status == "missing":
            existing_item.status = "missing"
            if battery is not None:
                session.add(
                    BatteryLifecycleEvent(
                        battery_id=battery.id,
                        event_type="manifest_missing",
                        description=f"Marked missing during manifest {manifest.id} receipt",
                        actor_id=current_user.id,
                    )
                )
        elif item_status == "extra":
            if battery is None:
                raise HTTPException(status_code=409, detail=f"Unable to resolve battery '{battery_serial}'")
            apply_battery_transition(
                session,
                battery=battery,
                to_status="available",
                to_location_type="warehouse",
                to_location_id=receiving_warehouse_id,
                event_type="manifest_extra",
                event_description=f"Extra battery found during manifest {manifest.id} receipt",
                actor_id=current_user.id,
            )
            existing_item.status = "extra"
        else:
            existing_item.status = "pending"
            if battery is not None:
                session.add(
                    BatteryLifecycleEvent(
                        battery_id=battery.id,
                        event_type="manifest_pending",
                        description=f"Marked pending in manifest {manifest.id} receipt",
                        actor_id=current_user.id,
                    )
                )

        session.add(existing_item)

    manifest.status = _compute_manifest_status(list(item_map.values()))
    session.add(manifest)

    manifest = _load_manifest_by_id(session, normalized_manifest_id)
    response = DataResponse(success=True, data=manifest)
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


@router.post("/{manifest_id}/process", response_model=DataResponse[ManifestRead])
def process_manifest(
    manifest_id: str,
    current_user: User = Depends(deps.require_internal_operator),
    session: Session = Depends(get_session),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """
    Mark a manifest as Processed once receipt is complete.
    """
    normalized_manifest_id = _normalize_manifest_id(manifest_id, field_name="manifest_id")
    payload = {"manifest_id": normalized_manifest_id}
    idempotency_key = normalize_idempotency_key(idempotency_key)
    request_path = f"/manifests/{normalized_manifest_id}/process"
    request_fingerprint = build_request_fingerprint(payload)
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

    manifest = _load_manifest_by_id(session, normalized_manifest_id, for_update=True)
    current_status = _normalize_manifest_status(manifest.status, field_name="manifest.status")
    manifest.status = current_status

    if current_status == "Processed":
        response = DataResponse(success=True, data=manifest)
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

    if current_status != "Received":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Manifest '{manifest.id}' must be 'Received' before processing. "
                f"Current status: '{current_status}'."
            ),
        )

    if any(item.status in {"pending", "missing"} for item in manifest.items):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Manifest '{manifest.id}' still has pending or missing items. "
                "Resolve receipt discrepancies before marking as Processed."
            ),
        )

    manifest.status = "Processed"
    session.add(manifest)
    manifest = _load_manifest_by_id(session, normalized_manifest_id)
    response = DataResponse(success=True, data=manifest)
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
