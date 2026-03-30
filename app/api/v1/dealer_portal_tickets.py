"""
Dealer Portal Tickets — Support ticket CRUD and reply system.
"""
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.support import SupportTicket, TicketMessage, TicketStatus, TicketPriority

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    subject: str
    description: str
    category: str = "general"
    priority: str = "medium"
    attachment_url: Optional[str] = None


class ReplyRequest(BaseModel):
    message: str
    attachment_url: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────

@router.get("")
def list_tickets(
    status_filter: Optional[str] = Query(None, description="open, in_progress, resolved, closed"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List dealer's support tickets with optional status filter."""
    query = select(SupportTicket).where(SupportTicket.user_id == current_user.id)

    if status_filter:
        query = query.where(SupportTicket.status == status_filter)

    query = query.order_by(SupportTicket.created_at.desc())

    total = db.exec(
        select(func.count(SupportTicket.id)).where(SupportTicket.user_id == current_user.id)
    ).one() or 0

    tickets = db.exec(query.offset((page - 1) * limit).limit(limit)).all()

    return {
        "tickets": [
            {
                "id": t.id,
                "subject": t.subject,
                "description": t.description,
                "status": t.status.value if hasattr(t.status, 'value') else t.status,
                "priority": t.priority.value if hasattr(t.priority, 'value') else t.priority,
                "category": t.category,
                "created_at": str(t.created_at),
                "updated_at": str(t.updated_at),
                "resolved_at": str(t.resolved_at) if t.resolved_at else None,
            }
            for t in tickets
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("")
def create_ticket(
    data: CreateTicketRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Create a new support ticket."""
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=data.subject,
        description=data.description,
        category=data.category,
        priority=TicketPriority(data.priority) if data.priority in [e.value for e in TicketPriority] else TicketPriority.MEDIUM,
        status=TicketStatus.OPEN,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Add initial message
    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message=data.description,
    )
    db.add(msg)
    db.commit()

    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "category": ticket.category,
        "created_at": str(ticket.created_at),
        "message": "Ticket created successfully",
    }


@router.get("/{ticket_id}")
def get_ticket_detail(
    ticket_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get ticket detail with all messages/replies."""
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    messages = db.exec(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at.asc())
    ).all()

    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status.value if hasattr(ticket.status, 'value') else ticket.status,
        "priority": ticket.priority.value if hasattr(ticket.priority, 'value') else ticket.priority,
        "category": ticket.category,
        "created_at": str(ticket.created_at),
        "updated_at": str(ticket.updated_at),
        "resolved_at": str(ticket.resolved_at) if ticket.resolved_at else None,
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "message": m.message,
                "is_internal": m.is_internal_note,
                "created_at": str(m.created_at),
            }
            for m in messages
        ],
    }


@router.post("/{ticket_id}/reply")
def reply_to_ticket(
    ticket_id: int,
    data: ReplyRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Reply to a ticket."""
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status in (TicketStatus.CLOSED,):
        raise HTTPException(status_code=400, detail="Cannot reply to a closed ticket")

    msg = TicketMessage(
        ticket_id=ticket_id,
        sender_id=current_user.id,
        message=data.message,
    )
    db.add(msg)

    ticket.updated_at = datetime.utcnow()
    if ticket.status == TicketStatus.RESOLVED:
        ticket.status = TicketStatus.OPEN  # Reopen if dealer replies after resolution
    db.add(ticket)
    db.commit()
    db.refresh(msg)

    return {
        "id": msg.id,
        "ticket_id": ticket_id,
        "message": msg.message,
        "created_at": str(msg.created_at),
    }


@router.patch("/{ticket_id}/close")
def close_ticket(
    ticket_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Close a ticket."""
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = TicketStatus.CLOSED
    ticket.resolved_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()
    db.add(ticket)
    db.commit()

    return {"message": "Ticket closed", "id": ticket_id}
