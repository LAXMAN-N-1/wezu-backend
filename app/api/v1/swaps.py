from __future__ import annotations
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from datetime import datetime, timezone; UTC = timezone.utc
from sqlmodel import Session, select
from app.api import deps
from app.api.deps import get_current_user
from app.core.audit import audit_log
from app.db.session import get_session
from app.models.battery import Battery, BatteryStatus, LocationType
from app.models.financial import Transaction, TransactionStatus, TransactionType, Wallet
from app.models.rental import Rental, RentalStatus
from app.models.station import Station
from app.models.user import User
from app.models.swap import SwapSession
from app.schemas.swap import SwapInitRequest, SwapResponse, SwapCompleteRequest
from app.services.dealer_station_service import DealerStationService
from app.services.swap_service import SwapService

router = APIRouter()


def _resolve_active_rental(
    session: Session,
    *,
    user_id: int,
    rental_id: Optional[int] = None,
) -> Optional[Rental]:
    statement = select(Rental).where(
        Rental.user_id == user_id,
        Rental.status == RentalStatus.ACTIVE,
    )
    if rental_id is not None:
        statement = statement.where(Rental.id == rental_id)
    return session.exec(statement.order_by(Rental.start_time.desc())).first()


def _pick_replacement_battery(
    session: Session,
    *,
    station_id: int,
    preferred_battery_type: Optional[str] = None,
) -> Optional[Battery]:
    statement = (
        select(Battery)
        .where(Battery.location_id == station_id)
        .where(Battery.location_type == LocationType.STATION)
        .where(Battery.status == BatteryStatus.AVAILABLE)
        .where(Battery.current_charge >= 80)
        .where(Battery.health_percentage >= 85)
        .order_by(Battery.current_charge.desc(), Battery.health_percentage.desc())
    )
    normalized_type = (preferred_battery_type or "").strip().lower()
    if normalized_type:
        statement = statement.where(Battery.battery_type.is_not(None)).where(
            Battery.battery_type.ilike(normalized_type)
        )
    return session.exec(statement).first()


@router.get("/suggestions")
def get_swap_suggestions(
    rental_id: Optional[int] = Query(default=None),
    user_latitude: Optional[float] = Query(default=None),
    user_longitude: Optional[float] = Query(default=None),
    battery_type: Optional[str] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Any:
    return SwapService.get_swap_suggestions(
        session,
        user_id=current_user.id,
        rental_id=rental_id,
        user_latitude=user_latitude,
        user_longitude=user_longitude,
        battery_type=battery_type,
        limit=limit,
    )


@router.post("/initiate", response_model=SwapResponse)
@audit_log("INITIATE_SWAP", "SWAP")
def initiate_swap(
    *,
    request: Request,
    session: Session = Depends(get_session),
    swap_in: SwapInitRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    User initiates a swap at a station.
    """
    is_operational, msg = DealerStationService.is_station_operational(session, swap_in.station_id)
    if not is_operational:
        raise HTTPException(status_code=400, detail=msg)

    station = session.get(Station, swap_in.station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    rental = _resolve_active_rental(
        session,
        user_id=current_user.id,
        rental_id=swap_in.rental_id,
    )
    if not rental:
        raise HTTPException(status_code=404, detail="Active rental not found")

    existing_open_request = session.exec(
        select(SwapSession)
        .where(SwapSession.user_id == current_user.id)
        .where(SwapSession.rental_id == rental.id)
        .where(SwapSession.status.in_(["initiated", "processing"]))
        .order_by(SwapSession.created_at.desc())
    ).first()
    if existing_open_request:
        existing_station = session.get(Station, existing_open_request.station_id)
        return {
            "id": existing_open_request.id,
            "status": existing_open_request.status,
            "station_id": existing_open_request.station_id,
            "station_name": existing_station.name if existing_station else None,
            "amount": float(existing_open_request.swap_amount or 0.0),
            "created_at": existing_open_request.created_at,
        }

    current_battery = session.get(Battery, rental.battery_id)
    if not current_battery:
        raise HTTPException(status_code=400, detail="Rental battery not found")

    replacement_battery_id = swap_in.new_battery_id
    if replacement_battery_id is not None:
        replacement_battery = session.get(Battery, replacement_battery_id)
        if not replacement_battery:
            raise HTTPException(status_code=404, detail="Requested replacement battery not found")
        if replacement_battery.status != BatteryStatus.AVAILABLE:
            raise HTTPException(status_code=400, detail="Requested replacement battery is not available")
        if (
            replacement_battery.location_type != LocationType.STATION
            or replacement_battery.location_id != station.id
        ):
            raise HTTPException(status_code=400, detail="Requested replacement battery is not at this station")
    else:
        replacement_battery = _pick_replacement_battery(
            session,
            station_id=station.id,
            preferred_battery_type=swap_in.preferred_battery_type,
        )
        if not replacement_battery:
            raise HTTPException(
                status_code=409,
                detail="No eligible charged batteries are available at this station",
            )
        replacement_battery_id = replacement_battery.id

    swap_fee = float(SwapService.calculate_swap_fee(rental.id, session))
    if swap_fee > 0:
        wallet = session.exec(select(Wallet).where(Wallet.user_id == current_user.id)).first()
        if not wallet or float(wallet.balance) < swap_fee:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance. Please recharge.")

    swap_session = SwapSession(
        rental_id=rental.id,
        user_id=current_user.id,
        station_id=station.id,
        old_battery_id=current_battery.id,
        new_battery_id=replacement_battery_id,
        old_battery_soc=float(current_battery.current_charge or 0.0),
        swap_amount=swap_fee,
        status="initiated",
        payment_status="pending",
    )
    session.add(swap_session)
    session.commit()
    session.refresh(swap_session)

    return {
        "id": swap_session.id,
        "status": swap_session.status,
        "station_id": station.id,
        "station_name": station.name,
        "amount": float(swap_session.swap_amount or 0.0),
        "created_at": swap_session.created_at,
    }


@router.post("/{swap_id}/complete", response_model=SwapResponse)
@audit_log("COMPLETE_SWAP", "SWAP", resource_id_param="swap_id")
def complete_swap(
    *,
    request: Request,
    session: Session = Depends(get_session),
    swap_id: int,
    complete_in: SwapCompleteRequest,
    # In production, this endpoint might be protected for IoT Station Callbacks only
    current_user: User = Depends(get_current_user), 
) -> Any:
    """
    Finalize swap after station confirms dispense.
    """
    swap_session = session.get(SwapSession, swap_id)
    if not swap_session:
        raise HTTPException(status_code=404, detail="Session not found")

    if swap_session.user_id != current_user.id:
        deps.require_internal_operator(current_user=current_user)

    if swap_session.status == "completed":
        raise HTTPException(status_code=400, detail="Swap already completed")

    if swap_session.rental_id is None:
        raise HTTPException(status_code=400, detail="Swap session is not linked to a rental")

    rental = session.get(Rental, swap_session.rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    if rental.status != RentalStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Rental is not active")

    replacement_battery_id = complete_in.new_battery_id or swap_session.new_battery_id
    if replacement_battery_id is None:
        raise HTTPException(status_code=400, detail="Replacement battery is required")

    swap_fee = float(SwapService.calculate_swap_fee(rental.id, session))
    wallet: Optional[Wallet] = None
    if swap_fee > 0:
        wallet = session.exec(
            select(Wallet).where(Wallet.user_id == swap_session.user_id).with_for_update()
        ).first()
        if wallet is None:
            raise HTTPException(status_code=400, detail="Wallet not found for swap payment")
        if float(wallet.balance) < swap_fee:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    try:
        swap_executed = SwapService.execute_swap(
            rental_id=swap_session.rental_id,
            new_battery_id=replacement_battery_id,
            station_id=swap_session.station_id,
            session=session,
            auto_commit=False,
        )
        if not swap_executed:
            raise HTTPException(status_code=400, detail="Swap execution failed")

        if swap_fee > 0 and wallet is not None:
            wallet.balance = float(wallet.balance) - swap_fee
            session.add(wallet)
            session.add(
                Transaction(
                    user_id=swap_session.user_id,
                    wallet_id=wallet.id,
                    amount=-swap_fee,
                    balance_after=float(wallet.balance),
                    type="debit",
                    category="swap_fee",
                    transaction_type=TransactionType.SWAP_FEE,
                    status=TransactionStatus.SUCCESS,
                    reference_type="swap_session",
                    reference_id=str(swap_session.id),
                    description=f"Swap fee charged for station #{swap_session.station_id}",
                )
            )

        swap_session.new_battery_id = replacement_battery_id
        swap_session.old_battery_soc = complete_in.old_battery_soc
        swap_session.new_battery_soc = complete_in.new_battery_soc
        swap_session.swap_amount = swap_fee
        swap_session.status = "completed"
        swap_session.payment_status = "paid"
        swap_session.completed_at = datetime.now(UTC)

        session.add(swap_session)
        session.commit()
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Swap completion failed: {exc}") from exc

    session.refresh(swap_session)

    return {
        "id": swap_session.id,
        "status": swap_session.status,
        "station_id": swap_session.station_id,
        "amount": float(swap_session.swap_amount or 0.0),
        "created_at": swap_session.created_at,
    }
