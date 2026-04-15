"""
Centralized dealer-scope helpers used by dealer portal endpoints to enforce
strict tenant isolation.

Policy (see PLAN: Tenant Isolation Verification And Hardening Gate):
- Dealer portal endpoints that accept path-bound resource IDs MUST validate
  that the target resource belongs to the caller's dealer scope before
  returning any data.
- Deny behavior is non-disclosive: raise HTTP 404 on cross-tenant access
  rather than 403 so callers cannot probe for resource existence.
- Every scope violation is logged to the ``security.scope_violation`` channel
  with request id, actor id, dealer id, target id, and endpoint, for
  downstream anomaly detection.
"""
from __future__ import annotations

from typing import Iterable, Optional

from fastapi import HTTPException, Request, status
from sqlmodel import Session, select

from app.core.logging import get_logger
from app.models.dealer import DealerProfile
from app.models.rbac import UserRole, Role
from app.models.rental import Rental
from app.models.station import Station
from app.models.user import User

logger = get_logger(__name__)


def _request_id(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    state = getattr(request, "state", None)
    rid = getattr(state, "request_id", None) if state is not None else None
    if rid:
        return str(rid)
    headers = getattr(request, "headers", None)
    if headers is not None:
        return headers.get("x-request-id")
    return None


def log_scope_violation(
    *,
    actor_id: Optional[int],
    dealer_id: Optional[int],
    target_id: Optional[int | str],
    endpoint: str,
    reason: str,
    request: Optional[Request] = None,
) -> None:
    """Emit a structured ``security.scope_violation`` event.

    Never raises — logging failures must not mask the underlying 404.
    """
    try:
        logger.warning(
            "security.scope_violation",
            actor_id=actor_id,
            dealer_id=dealer_id,
            target_id=target_id,
            endpoint=endpoint,
            reason=reason,
            request_id=_request_id(request),
        )
    except Exception:  # pragma: no cover - logging must never break requests
        pass


def dealer_station_ids(db: Session, dealer: DealerProfile) -> list[int]:
    rows = db.exec(select(Station.id).where(Station.dealer_id == dealer.id)).all()
    return [rid for rid in rows]


def user_in_dealer_scope(
    db: Session,
    dealer: DealerProfile,
    target_user_id: int,
) -> bool:
    """A user is in dealer scope when any of the following is true:

    - The user was provisioned by the dealer (``created_by_dealer_id``).
    - The user holds a ``UserRole`` pointing to a Role owned by the dealer.
    - The user has a rental at one of the dealer's stations (customer scope).
    """
    target = db.get(User, target_user_id)
    if not target:
        return False

    if getattr(target, "created_by_dealer_id", None) == dealer.id:
        return True

    linked_role = db.exec(
        select(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id == target_user_id, Role.dealer_id == dealer.id)
    ).first()
    if linked_role:
        return True

    station_ids = dealer_station_ids(db, dealer)
    if station_ids:
        rental = db.exec(
            select(Rental.id).where(
                Rental.user_id == target_user_id,
                Rental.start_station_id.in_(station_ids),
            )
        ).first()
        if rental:
            return True

    return False


def role_in_dealer_scope(db: Session, dealer: DealerProfile, role_id: int) -> Optional[Role]:
    """Return the Role if the role belongs to the dealer's scope, else None.

    Roles with ``dealer_id`` set must match the caller dealer. Global
    system roles (``dealer_id is None``) are NOT considered in-scope for
    dealer-portal mutation endpoints.
    """
    role = db.get(Role, role_id)
    if not role:
        return None
    if role.dealer_id != dealer.id:
        return None
    return role


def assert_rental_in_dealer_scope(
    db: Session,
    dealer: DealerProfile,
    rental_id: int,
) -> Rental:
    """Load a rental and ensure it belongs to one of the dealer's stations.

    Returns the Rental on success; raises ``HTTPException(404)`` otherwise.
    Callers should catch/log the violation around this function when they
    need to attribute the actor and endpoint.
    """
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    station_ids = set(dealer_station_ids(db, dealer))
    if not station_ids or rental.start_station_id not in station_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return rental


def txn_in_dealer_scope(
    db: Session,
    dealer: DealerProfile,
    prefix: str,
    db_id: int,
) -> bool:
    """Validate a ledger entry (rental/commission) belongs to the dealer."""
    if prefix == "RENTAL":
        rental = db.get(Rental, db_id)
        if not rental:
            return False
        station_ids = set(dealer_station_ids(db, dealer))
        return bool(station_ids) and rental.start_station_id in station_ids
    if prefix == "COMM":
        from app.models.commission import CommissionLog

        entry = db.get(CommissionLog, db_id)
        if not entry:
            return False
        # CommissionLog.dealer_id references users.id (dealer owner user id)
        return entry.dealer_id == dealer.user_id
    return False
