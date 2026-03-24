"""
Dealer Portal Customers — Customer list, detail, and active rentals.
"""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from datetime import datetime

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.station import Station

router = APIRouter()


def _get_dealer_station_ids(db: Session, user_id: int) -> list:
    dealer = db.exec(
        select(DealerProfile).where(DealerProfile.user_id == user_id)
    ).first()
    if not dealer:
        raise HTTPException(status_code=403, detail="Not a dealer")
    stations = db.exec(
        select(Station).where(Station.dealer_id == dealer.id)
    ).all()
    return [s.id for s in stations]


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

        result = []
        for r in rentals:
            customer = db.get(User, r.user_id)
            battery = db.get(Battery, r.battery_id) if r.battery_id else None
            station = db.get(Station, r.start_station_id) if r.start_station_id else None

            result.append({
                "rental_id": r.id,
                "customer_name": customer.full_name if customer else "Unknown",
                "customer_id": r.user_id,
                "battery_serial": battery.serial_number if battery else "N/A",
                "battery_health": battery.health_percentage if battery else 0,
                "station_name": station.name if station else "N/A",
                "start_time": str(r.created_at),
                "duration_hours": round((datetime.utcnow() - r.created_at).total_seconds() / 3600, 1) if r.created_at else 0,
                "status": r.status,
            })

        return {"rentals": result, "total": len(result)}
    except Exception as e:
        return {"rentals": [], "total": 0, "error": str(e)}


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

        # Get distinct customer IDs
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

        total = len(customer_ids)
        users = db.exec(query.offset((page - 1) * limit).limit(limit)).all()

        customers = []
        for u in users:
            rental_count = db.exec(
                select(func.count(Rental.id)).where(
                    Rental.user_id == u.id,
                    Rental.start_station_id.in_(station_ids),
                )
            ).one() or 0

            customers.append({
                "id": u.id,
                "full_name": u.full_name or "Unknown",
                "email": u.email,
                "phone_number": u.phone_number,
                "total_rentals": rental_count,
                "last_login": str(u.last_login) if u.last_login else None,
                "created_at": str(u.created_at),
            })

        return {"customers": customers, "total": total, "page": page, "limit": limit}
    except Exception as e:
        return {"customers": [], "total": 0, "error": str(e)}


@router.get("/{customer_id}")
def get_customer_detail(
    customer_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Customer detail with rental history at this dealer's stations."""
    station_ids = _get_dealer_station_ids(db, current_user.id)
    customer = db.get(User, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        from app.models.rental import Rental

        rentals = db.exec(
            select(Rental).where(
                Rental.user_id == customer_id,
                Rental.start_station_id.in_(station_ids),
            ).order_by(Rental.created_at.desc())
        ).all()

        rental_list = []
        for r in rentals:
            station = db.get(Station, r.start_station_id) if r.start_station_id else None
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
        return {
            "id": customer.id,
            "full_name": customer.full_name,
            "email": customer.email,
            "phone_number": customer.phone_number,
            "total_rentals": 0,
            "rentals": [],
            "error": str(e),
        }
