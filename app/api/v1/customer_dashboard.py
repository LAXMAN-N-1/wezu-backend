"""Customer Dashboard — Aggregated stats for the customer home screen."""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from app.api import deps
from app.models.user import User
from app.models.rental import Rental
from app.models.financial import Wallet

router = APIRouter()


@router.get("/stats")
async def dashboard_stats(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    """
    Aggregate stats for the customer dashboard.
    Returns: active_rentals, total_rentals, wallet_balance, reward_points, carbon_saved_kg
    """
    # Active rental count
    active_count = db.exec(
        select(func.count(Rental.id)).where(
            Rental.user_id == current_user.id,
            Rental.status == "active",
        )
    ).one() or 0

    # Total rentals (all statuses)
    total_count = db.exec(
        select(func.count(Rental.id)).where(
            Rental.user_id == current_user.id,
        )
    ).one() or 0

    # Wallet balance
    wallet = db.exec(
        select(Wallet).where(Wallet.user_id == current_user.id)
    ).first()

    # Carbon savings estimate (~120g CO2 saved per km vs petrol 2-wheeler)
    # Using total_amount as proxy: avg ₹3/km → distance = total / 3
    total_amount_sum = db.exec(
        select(func.sum(Rental.total_amount)).where(
            Rental.user_id == current_user.id,
            Rental.status == "completed",
        )
    ).one() or 0.0

    # Rough estimate: ₹149/day = ~40km/day → 0.27 km per rupee → 0.12 kg CO2 per km
    estimated_distance_km = float(total_amount_sum) / 3.7  # avg ₹3.7/km
    carbon_saved_kg = round(estimated_distance_km * 0.12, 1)

    return {
        "active_rentals": active_count,
        "total_rentals": total_count,
        "wallet_balance": round(wallet.balance, 2) if wallet else 0.0,
        "reward_points": 0,  # Placeholder for MVP — no loyalty system yet
        "carbon_saved_kg": carbon_saved_kg,
    }
