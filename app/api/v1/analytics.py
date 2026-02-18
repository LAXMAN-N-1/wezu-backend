"""
Customer Analytics and Dashboard API
Personal stats, usage patterns, and insights
"""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.schemas.common import DataResponse

router = APIRouter()

@router.get("/dashboard", response_model=DataResponse[dict])
def get_dashboard(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get customer dashboard
    Shows active rentals, spending, favorite stations, etc.
    """
    dashboard = AnalyticsService.get_customer_dashboard(current_user.id, session)
    
    return DataResponse(
        success=True,
        data=dashboard
    )

@router.get("/rental-history", response_model=DataResponse[dict])
def get_rental_history_stats(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get rental history statistics"""
    stats = AnalyticsService.get_rental_history_stats(current_user.id, session)
    
    return DataResponse(
        success=True,
        data=stats
    )

@router.get("/cost-analytics", response_model=DataResponse[dict])
def get_cost_analytics(
    months: int = Query(3, ge=1, le=12),
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get cost analytics
    Monthly breakdown of spending
    """
    analytics = AnalyticsService.get_cost_analytics(current_user.id, months, session)
    
    return DataResponse(
        success=True,
        data=analytics
    )

@router.get("/usage-patterns", response_model=DataResponse[dict])
def get_usage_patterns(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get usage patterns
    Most active day/hour, average duration, etc.
    """
    patterns = AnalyticsService.get_usage_patterns(current_user.id, session)
    
    return DataResponse(
        success=True,
        data=patterns
    )

@router.get("/carbon-savings", response_model=DataResponse[dict])
async def get_carbon_savings(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Calculate carbon savings from battery usage"""
    from app.models.rental import Rental
    from sqlmodel import select
    
    # Get all completed rentals
    statement = select(Rental).where(
        Rental.user_id == current_user.id,
        Rental.status == "completed"
    )
    rentals = session.exec(statement).all()
    
    # Calculate carbon savings (Assume 1 hour usage saves 0.5 kg CO2)
    total_hours = 0.0
    for rental in rentals:
        if rental.actual_end_time and rental.start_time:
            duration = (rental.actual_end_time - rental.start_time).total_seconds() / 3600
            total_hours += duration
    
    carbon_saved_kg = total_hours * 0.5
    trees_equivalent = carbon_saved_kg / 21
    
    return DataResponse(
        success=True,
        data={
            "total_rentals": len(rentals),
            "total_hours": round(total_hours, 2),
            "carbon_saved_kg": round(carbon_saved_kg, 2),
            "trees_equivalent": round(trees_equivalent, 2),
            "comparison": {
                "car_km_saved": round(carbon_saved_kg * 5, 2),
                "plastic_bottles_saved": int(carbon_saved_kg * 50)
            }
        }
    )

@router.get("/export")
async def export_analytics_data(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session),
    format: str = "json"
):
    """Export user analytics data"""
    from app.models.rental import Rental
    from app.models.financial import Transaction
    from sqlmodel import select
    import datetime
    
    # Get rentals
    rentals_stmt = select(Rental).where(Rental.user_id == current_user.id)
    rentals = session.exec(rentals_stmt).all()
    
    # Get transactions
    txn_stmt = select(Transaction).where(Transaction.user_id == current_user.id)
    transactions = session.exec(txn_stmt).all()
    
    data = {
        "user_id": current_user.id,
        "export_date": datetime.datetime.utcnow().isoformat(),
        "rentals": [
            {
                "id": r.id,
                "battery_id": r.battery_id,
                "start_time": r.start_time.isoformat() if r.start_time else None,
                "end_time": r.end_time.isoformat() if r.end_time else None,
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
        ]
    }
    
    return DataResponse(success=True, data=data)
