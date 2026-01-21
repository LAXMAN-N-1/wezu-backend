"""
Enhanced Rental Endpoints
Additional rental operations including issue reporting and receipts
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api import deps
from app.models.user import User
from app.models.rental import Rental
from app.db.session import get_session
from pydantic import BaseModel

router = APIRouter()


class IssueReport(BaseModel):
    issue_type: str
    description: str
    severity: str = "medium"


@router.post("/{rental_id}/report-issue")
async def report_rental_issue(
    rental_id: int,
    issue: IssueReport,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Report an issue with a rental"""
    rental = db.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    # Create support ticket for the issue
    from app.models.support import SupportTicket
    
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=f"Rental Issue - {issue.issue_type}",
        description=f"Rental ID: {rental_id}\n{issue.description}",
        category="rental_issue",
        priority=issue.severity,
        status="open"
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    return {
        "message": "Issue reported successfully",
        "ticket_id": ticket.id,
        "status": "open"
    }


@router.get("/{rental_id}/receipt")
async def get_rental_receipt(
    rental_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(get_session)
):
    """Get rental receipt"""
    rental = db.get(Rental, rental_id)
    if not rental or rental.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rental not found")
    
    return {
        "rental_id": rental.id,
        "battery_id": rental.battery_id,
        "start_time": rental.start_time,
        "end_time": rental.end_time,
        "rental_fee": rental.rental_fee,
        "late_fee": rental.late_fee if hasattr(rental, 'late_fee') else 0,
        "total_fee": rental.total_fee if hasattr(rental, 'total_fee') else rental.rental_fee,
        "receipt_url": f"/receipts/rental_{rental.id}.pdf"
    }
