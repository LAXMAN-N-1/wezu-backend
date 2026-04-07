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
def report_rental_issue(
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
    from app.models.support import SupportTicket, TicketMessage
    from app.services.workflow_automation_service import WorkflowAutomationService
    
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=f"Rental Issue - {issue.issue_type}",
        category="rental_issue",
        priority=issue.severity,
        status="open"
    )
    db.add(ticket)
    db.flush()

    db.add(
        TicketMessage(
            ticket_id=ticket.id,
            sender_id=current_user.id,
            message=f"Rental ID: {rental_id}\n{issue.description}",
            is_internal_note=False,
        )
    )
    db.commit()
    db.refresh(ticket)
    WorkflowAutomationService.notify_support_ticket_created(
        db,
        user_id=current_user.id,
        ticket_id=ticket.id,
        subject=ticket.subject,
        priority=ticket.priority,
    )
    
    return {
        "message": "Issue reported successfully",
        "ticket_id": ticket.id,
        "status": "open"
    }


@router.get("/{rental_id}/receipt")
def get_rental_receipt(
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
        "rental_fee": float(rental.total_amount),
        "late_fee": float(rental.late_fee),
        "total_fee": float(rental.total_amount + rental.late_fee),
        "receipt_url": f"/receipts/rental_{rental.id}.pdf"
    }
