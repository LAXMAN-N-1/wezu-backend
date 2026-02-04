from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api.deps import get_current_active_user
from app.db.session import get_session
from app.models.user import User
from app.models.support import SupportTicket, TicketMessage
from app.schemas.support import (
    TicketCreate, TicketMessageCreate, 
    SupportTicketResponse, SupportTicketDetailResponse
)

router = APIRouter()

@router.post("/", response_model=SupportTicketResponse)
def create_ticket(
    *,
    session: Session = Depends(get_session),
    ticket_in: TicketCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Create a new support ticket.
    """
    # 1. Create Ticket
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=ticket_in.subject,
        category=ticket_in.category,
        priority=ticket_in.priority
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    
    # 2. Add Initial Message
    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message=ticket_in.description
    )
    session.add(message)
    session.commit()
    
    return ticket

@router.get("/", response_model=List[SupportTicketResponse])
def read_my_tickets(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    List current user's tickets.
    """
    return session.exec(select(SupportTicket).where(SupportTicket.user_id == current_user.id)).all()

@router.get("/{ticket_id}", response_model=SupportTicketDetailResponse)
def read_ticket_detail(
    *,
    session: Session = Depends(get_session),
    ticket_id: int,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Get detailed thread.
    """
    ticket = session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    # Check permissions (Owner or Admin)
    # Mock admin check for now
    if ticket.user_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not permitted")
         
    return ticket

@router.post("/{ticket_id}/reply", response_model=SupportTicketDetailResponse)
def reply_ticket(
    *,
    session: Session = Depends(get_session),
    ticket_id: int,
    reply_in: TicketMessageCreate,
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    Add a response to the ticket.
    """
    ticket = session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message=reply_in.message,
        is_internal_note=reply_in.is_internal_note
    )
    session.add(msg)
    
    # Auto-reopen if closed
    if ticket.status == "closed":
        ticket.status = "open"
        session.add(ticket)
        
    session.commit()
    session.refresh(ticket)
    return ticket
