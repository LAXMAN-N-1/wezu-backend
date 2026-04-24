from __future__ import annotations
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.api import deps
from app.models.user import User
from app.models.support import SupportTicket, TicketStatus, TicketPriority
from app.schemas.support import (
    SupportTicketResponse, SupportTicketDetailResponse,
    AgentPerformanceResponse, QueueStatsResponse
)
from app.services.support_service import SupportService

router = APIRouter()

@router.get("/tickets", response_model=List[SupportTicketResponse])
def read_all_tickets(
    *,
    session: Session = Depends(deps.get_db),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    agent_id: Optional[int] = None,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: all tickets with filters (status, priority, agent)"""
    statement = select(SupportTicket)
    if status:
        statement = statement.where(SupportTicket.status == status)
    if priority:
        statement = statement.where(SupportTicket.priority == priority)
    if agent_id:
        statement = statement.where(SupportTicket.assigned_to == agent_id)
        
    return session.exec(statement).all()

@router.put("/tickets/{ticket_id}/assign", response_model=SupportTicketResponse)
def assign_ticket(
    ticket_id: int,
    agent_id: int = Query(...),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
):
    """Admin: assign ticket to a support agent"""
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.assigned_to = agent_id
    ticket.status = TicketStatus.IN_PROGRESS
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

@router.put("/tickets/{ticket_id}/priority", response_model=SupportTicketResponse)
def update_ticket_priority(
    ticket_id: int,
    priority: TicketPriority = Query(...),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
):
    """Admin: change ticket priority"""
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.priority = priority
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

@router.put("/tickets/{ticket_id}/status", response_model=SupportTicketResponse)
def update_ticket_status(
    ticket_id: int,
    status: TicketStatus = Query(...),
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
):
    """Admin: update ticket status"""
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    ticket.status = status
    if status == TicketStatus.RESOLVED:
        from datetime import datetime, timezone; UTC = timezone.utc
        ticket.resolved_at = datetime.now(UTC)
        
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

@router.get("/agents/performance", response_model=List[AgentPerformanceResponse])
def get_agents_performance(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
):
    """Per-agent metrics: resolution time, CSAT, tickets resolved"""
    return SupportService.get_agent_performance(db)

@router.get("/queue-stats", response_model=QueueStatsResponse)
def get_overall_queue_stats(
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db)
):
    """Queue overview: open, overdue, by priority counts"""
    return SupportService.get_queue_stats(db)
