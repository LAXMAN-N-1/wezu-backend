from __future__ import annotations
"""
Dealer Portal Customers — Customer list, detail, and active rentals.
"""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select, func
from datetime import datetime, timezone; UTC = timezone.utc
import logging

from app.core.dealer_scope import log_scope_violation
from app.db.session import get_session

logger = logging.getLogger(__name__)
from app.api import deps
from app.api.deps import get_current_user
from app.models.user import User
from app.models.station import Station

router = APIRouter()


def _get_dealer_station_ids(db: Session, user_id: int) -> list:
    dealer = deps.get_dealer_profile_or_403(db, user_id, detail="Not a dealer")
    # Select only IDs — avoids loading full Station objects
    ids = db.exec(
        select(Station.id).where(Station.dealer_id == dealer.id)
    ).all()
    return list(ids)


@router.get("/rentals/active")
def get_active_rentals(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Live table of batteries currently rented from dealer's stations."""
    station_ids = _get_dealer_station_ids(db, current_user.id)
    if not station_ids:
        return {"rentals": [], "total": 0}

    try:
        from app.models.rental import Rental
        from app.models.battery import Battery

        rentals = db.exec(
            select(Rental)
            .where(
                Rental.start_station_id.in_(station_ids),
                Rental.status == "active",
            )
            .order_by(Rental.created_at.desc())
        ).all()

        # Batch-load related entities (eliminates 3 N+1 queries per rental)
        user_ids = list({r.user_id for r in rentals if r.user_id})
        battery_ids = list({r.battery_id for r in rentals if r.battery_id})
        stn_ids = list({r.start_station_id for r in rentals if r.start_station_id})

        users_map = {u.id: u for u in db.exec(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
        batteries_map = {b.id: b for b in db.exec(select(Battery).where(Battery.id.in_(battery_ids))).all()} if battery_ids else {}
        stations_map = {s.id: s for s in db.exec(select(Station).where(Station.id.in_(stn_ids))).all()} if stn_ids else {}

        result = []
        for r in rentals:
            customer = users_map.get(r.user_id)
            battery = batteries_map.get(r.battery_id)
            station = stations_map.get(r.start_station_id)

            result.append({
                "rental_id": r.id,
                "customer_name": customer.full_name if customer else "Unknown",
                "customer_id": r.user_id,
                "battery_serial": battery.serial_number if battery else "N/A",
                "battery_health": battery.health_percentage if battery else 0,
                "station_name": station.name if station else "N/A",
                "start_time": str(r.created_at),
                "duration_hours": round((datetime.now(UTC) - r.created_at).total_seconds() / 3600, 1) if r.created_at else 0,
                "status": r.status,
            })

        return {"rentals": result, "total": len(result)}
    except Exception as e:
        logger.exception("customer_active_rentals_failed")
        return {"rentals": [], "total": 0, "error": "Failed to fetch rentals"}


@router.get("")
def list_customers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List all customers who have rented from this dealer's stations."""
    station_ids = _get_dealer_station_ids(db, current_user.id)
    if not station_ids:
        return {"customers": [], "total": 0}

    try:
        from app.models.rental import Rental

        # Get distinct customer IDs for the page query
        customer_query = (
            select(Rental.user_id)
            .where(Rental.start_station_id.in_(station_ids))
            .distinct()
        )
        customer_ids = [row for row in db.exec(customer_query).all()]

        if not customer_ids:
            return {"customers": [], "total": 0}

        query = select(User).where(User.id.in_(customer_ids))
        if search:
            query = query.where(
                User.full_name.ilike(f"%{search}%") |
                User.email.ilike(f"%{search}%") |
                User.phone_number.ilike(f"%{search}%")
            )

        # Use SQL COUNT instead of Python len() on full ID list
        total = db.exec(
            select(func.count()).select_from(query.subquery())
        ).one()
        users = db.exec(query.offset((page - 1) * limit).limit(limit)).all()

        # Batch rental-count for this page of users (eliminates N+1 COUNT per user)
        page_user_ids = [u.id for u in users]
        rental_counts_rows = db.exec(
            select(Rental.user_id, func.count(Rental.id))
            .where(
                Rental.user_id.in_(page_user_ids),
                Rental.start_station_id.in_(station_ids),
            )
            .group_by(Rental.user_id)
        ).all() if page_user_ids else []
        rental_count_map = {row[0]: row[1] for row in rental_counts_rows}

        customers = []
        for u in users:
            customers.append({
                "id": u.id,
                "full_name": u.full_name or "Unknown",
                "email": u.email,
                "phone_number": u.phone_number,
                "total_rentals": rental_count_map.get(u.id, 0),
                "last_login": str(u.last_login) if u.last_login else None,
                "created_at": str(u.created_at),
            })

        return {"customers": customers, "total": total, "page": page, "limit": limit}
    except Exception as e:
        logger.exception("list_customers_failed")
        return {"customers": [], "total": 0, "error": "Failed to fetch customers"}


@router.get("/{customer_id}")
def get_customer_detail(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Customer detail with rental history at this dealer's stations.

    Strict dealer-scope enforcement: the caller may only read a customer
    when that customer has at least one rental at one of the caller's
    stations. Cross-tenant probes return 404 (non-disclosive).
    """
    station_ids = _get_dealer_station_ids(db, current_user.id)

    from app.models.rental import Rental

    # Prove dealer<->customer relationship BEFORE fetching any PII. Using
    # a lightweight existence check keeps this cheap for large tenants.
    proof = None
    if station_ids:
        proof = db.exec(
            select(Rental.id).where(
                Rental.user_id == customer_id,
                Rental.start_station_id.in_(station_ids),
            ).limit(1)
        ).first()

    if not proof:
        log_scope_violation(
            actor_id=current_user.id,
            dealer_id=None,
            target_id=customer_id,
            endpoint="GET /dealer/portal/customers/{customer_id}",
            reason="customer_not_in_dealer_scope",
            request=request,
        )
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = db.get(User, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        rentals = db.exec(
            select(Rental).where(
                Rental.user_id == customer_id,
                Rental.start_station_id.in_(station_ids),
            ).order_by(Rental.created_at.desc())
        ).all()

        # Batch-load stations (eliminates N+1 per rental)
        rental_stn_ids = list({r.start_station_id for r in rentals if r.start_station_id})
        stations_map = {s.id: s for s in db.exec(select(Station).where(Station.id.in_(rental_stn_ids))).all()} if rental_stn_ids else {}

        rental_list = []
        for r in rentals:
            station = stations_map.get(r.start_station_id)
            rental_list.append({
                "rental_id": r.id,
                "station_name": station.name if station else "N/A",
                "status": r.status,
                "start_time": str(r.created_at),
                "end_time": str(r.updated_at) if r.status != "active" else None,
            })

        return {
            "id": customer.id,
            "full_name": customer.full_name,
            "email": customer.email,
            "phone_number": customer.phone_number,
            "total_rentals": len(rental_list),
            "rentals": rental_list,
        }
    except Exception as e:
        logger.exception("customer_detail_failed", extra={"customer_id": customer.id})
        return {
            "id": customer.id,
            "full_name": customer.full_name,
            "email": customer.email,
            "phone_number": customer.phone_number,
            "total_rentals": 0,
            "rentals": [],
            "error": "Failed to fetch customer detail",
        }
