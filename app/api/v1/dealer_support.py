from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.support import SupportTicket, TicketMessage, TicketPriority
from app.schemas.support import (
    TicketCreate, TicketMessageCreate, 
    SupportTicketResponse, SupportTicketDetailResponse,
    TicketMetricsResponse, TicketRatingUpdate, TicketStatusUpdate,
    TicketActionUpdate
)
from app.schemas.common import DataResponse
from app.services.support_service import SupportService
from datetime import datetime

router = APIRouter()

@router.post("/", response_model=SupportTicketResponse)
def create_dealer_ticket(
    *,
    session: Session = Depends(get_db),
    ticket_in: TicketCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Dealer: raise a new support ticket"""
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=ticket_in.subject,
        category=ticket_in.category,
        priority=ticket_in.priority,
        description=ticket_in.description,
        attachment_urls=ticket_in.attachment_urls or []
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    
    SupportService.handle_new_ticket_message(
        db=session,
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message_text=ticket_in.description,
        attachment_urls=ticket_in.attachment_urls
    )
    return ticket

@router.get("/", response_model=List[SupportTicketResponse])
def read_dealer_tickets(
    *,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    priority: Optional[TicketPriority] = None,
    category: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    station_id: Optional[int] = None,
) -> Any:
    """Dealer: list their own tickets with advanced filters"""
    statement = select(SupportTicket).where(SupportTicket.user_id == current_user.id)
    
    if priority:
        statement = statement.where(SupportTicket.priority == priority)
    if category:
        statement = statement.where(SupportTicket.category == category)
    if assigned_to_id:
        statement = statement.where(SupportTicket.assigned_to_id == assigned_to_id)
    if start_date:
        statement = statement.where(SupportTicket.created_at >= start_date)
    if end_date:
        statement = statement.where(SupportTicket.created_at <= end_date)
    if station_id:
        statement = statement.where(SupportTicket.station_id == station_id)
        
    return session.exec(statement.order_by(SupportTicket.created_at.desc())).all()

@router.get("/metrics", response_model=TicketMetricsResponse)
def get_dealer_ticket_metrics(
    *,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Dealer: get ticket metrics and KPIs"""
    return SupportService.get_dealer_ticket_metrics(session, current_user.id)

@router.get("/{ticket_id}", response_model=SupportTicketDetailResponse)
def read_ticket_detail(
    *,
    session: Session = Depends(get_db),
    ticket_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Dealer: get ticket summary and full thread"""
    ticket = session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    if ticket.user_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not permitted")
         
    # Embed customer ticket history
    history = session.exec(
        select(SupportTicket)
        .where(SupportTicket.user_id == ticket.user_id)
        .where(SupportTicket.id != ticket.id)
        .order_by(SupportTicket.created_at.desc())
        .limit(10)
    ).all()
    
    # Embed related tickets (same station or linked)
    related = session.exec(
        select(SupportTicket)
        .where(
            (SupportTicket.related_to_id == ticket.id) | 
            (SupportTicket.station_id == ticket.station_id if ticket.station_id else False)
        )
        .where(SupportTicket.id != ticket.id)
        .limit(10)
    ).all()
    
    # Populate and return the response
    return SupportTicketDetailResponse(
        **ticket.model_dump(),
        messages=ticket.messages,
        customer_history=history,
        related_tickets=related
    )

@router.post("/{ticket_id}/reply", response_model=SupportTicketDetailResponse)
def reply_ticket(
    *,
    session: Session = Depends(get_db),
    ticket_id: int,
    reply_in: TicketMessageCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Dealer: add a response to the ticket"""
    ticket = session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not permitted")

    msg, created = SupportService.handle_new_ticket_message(
        db=session,
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message_text=reply_in.message,
        attachment_urls=reply_in.attachment_urls
    )
    
    if not created:
        raise HTTPException(status_code=400, detail="Duplicate message: This message has already been sent to this ticket.")
    
    if ticket.status == "closed":
        ticket.status = "open"
        session.add(ticket)
        
    session.commit()
    session.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/rate", response_model=SupportTicketResponse)
def rate_ticket(
    *,
    session: Session = Depends(get_db),
    ticket_id: int,
    rating_in: TicketRatingUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Dealer: rate a resolved/closed support ticket"""
    try:
        ticket = SupportService.rate_ticket(
            db=session,
            ticket_id=ticket_id,
            dealer_id=current_user.id,
            rating=rating_in.rating
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{ticket_id}/status", response_model=SupportTicketResponse)
def update_dealer_ticket_status(
    *,
    session: Session = Depends(get_db),
    ticket_id: int,
    action_in: TicketActionUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Dealer: escalate, change priority, or update ticket status"""
    try:
        ticket = SupportService.update_ticket_action(
            db=session,
            ticket_id=ticket_id,
            dealer_id=current_user.id,
            action_in=action_in
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
