"""
Enhanced Analytics Endpoints
Additional analytics including carbon savings and data export
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.api import deps
from app.models.user import User
from app.db.session import get_session
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/carbon-savings")
async def get_carbon_savings(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Calculate carbon savings from battery usage"""
    from app.models.rental import Rental
    from sqlmodel import select
    
    # Get all completed rentals
    statement = select(Rental).where(
        (Rental.user_id == current_user.id) &
        (Rental.status == "completed")
    )
    rentals = db.exec(statement).all()
    
    # Calculate carbon savings
    # Assume 1 hour of battery usage saves 0.5 kg CO2
    total_hours = 0
    for rental in rentals:
        if rental.actual_end_time and rental.start_time:
            duration = (rental.actual_end_time - rental.start_time).total_seconds() / 3600
            total_hours += duration
    
    carbon_saved_kg = total_hours * 0.5
    trees_equivalent = carbon_saved_kg / 21  # 1 tree absorbs ~21kg CO2/year
    
    return {
        "total_rentals": len(rentals),
        "total_hours": round(total_hours, 2),
        "carbon_saved_kg": round(carbon_saved_kg, 2),
        "trees_equivalent": round(trees_equivalent, 2),
        "comparison": {
            "car_km_saved": round(carbon_saved_kg * 5, 2),  # 1kg CO2 = ~5km car travel
            "plastic_bottles_saved": round(carbon_saved_kg * 50, 0)
        }
    }


@router.get("/export")
async def export_analytics_data(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session),
    format: str = "json"
):
    """Export user analytics data"""
    from app.models.rental import Rental
    from app.models.financial import Transaction
    from sqlmodel import select
    
    # Get rentals
    rentals_stmt = select(Rental).where(Rental.user_id == current_user.id)
    rentals = db.exec(rentals_stmt).all()
    
    # Get transactions
    txn_stmt = select(Transaction).where(Transaction.user_id == current_user.id)
    transactions = db.exec(txn_stmt).all()
    
    data = {
        "user_id": current_user.id,
        "export_date": datetime.utcnow().isoformat(),
        "rentals": [
            {
                "id": r.id,
                "battery_id": r.battery_id,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "rental_fee": r.rental_fee,
                "status": r.status
            }
            for r in rentals
        ],
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "type": t.transaction_type,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in transactions
        ],
        "summary": {
            "total_rentals": len(rentals),
            "total_spent": sum(t.amount for t in transactions if t.transaction_type == "debit"),
            "total_received": sum(t.amount for t in transactions if t.transaction_type == "credit")
        }
    }
    
    if format == "csv":
        # In production, convert to CSV
        return {"message": "CSV export not yet implemented", "data": data}
    
    return data
