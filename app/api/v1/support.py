from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from sqlmodel import Session, select
from app.api.deps import get_current_user
from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.support import SupportTicket, TicketMessage
from app.models.faq import FAQ
from app.schemas.support import (
    TicketCreate, TicketMessageCreate, 
    SupportTicketResponse, SupportTicketDetailResponse
)
import os
import shutil

router = APIRouter()

@router.get("/admin/tickets", response_model=List[SupportTicketResponse])
def admin_read_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: list all support tickets with filters"""
    statement = select(SupportTicket)
    if status:
        statement = statement.where(SupportTicket.status == status)
    if category:
        statement = statement.where(SupportTicket.category == category)
    return session.exec(statement.order_by(SupportTicket.created_at.desc())).all()

@router.post("/tickets", response_model=SupportTicketResponse)
def create_ticket(
    *,
    session: Session = Depends(get_session),
    ticket_in: TicketCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Customer: raise a new support ticket"""
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=ticket_in.subject,
        category=ticket_in.category,
        priority=ticket_in.priority
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    
    from app.services.support_service import SupportService
    SupportService.handle_new_ticket_message(
        db=session,
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message_text=ticket_in.description
    )
    return ticket

@router.get("/tickets/my", response_model=List[SupportTicketResponse])
def read_my_tickets(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Customer: list their own tickets"""
    return session.exec(select(SupportTicket).where(SupportTicket.user_id == current_user.id)).all()

@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetailResponse)
def read_ticket_detail(
    *,
    session: Session = Depends(get_session),
    ticket_id: int,
    current_user: User = Depends(get_current_user),
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

@router.post("/tickets/{ticket_id}/reply", response_model=SupportTicketDetailResponse)
def reply_ticket(
    *,
    session: Session = Depends(get_session),
    ticket_id: int,
    reply_in: TicketMessageCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Add a response to the ticket.
    """
    ticket = session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Add Message & Check for Auto-Response
    from app.services.support_service import SupportService
    SupportService.handle_new_ticket_message(
        db=session,
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message_text=reply_in.message
    )
    
    # Auto-reopen if closed
    if ticket.status == "closed":
        ticket.status = "open"
        session.add(ticket)
        
    session.commit()
    session.refresh(ticket)
    return ticket

@router.put("/tickets/{ticket_id}/close", response_model=SupportTicketResponse)
def close_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Customer: close a resolved ticket"""
    from app.models.support import TicketStatus
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.status = TicketStatus.CLOSED
    ticket.updated_at = datetime.utcnow()
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

# --- Live Chat ---
from app.schemas.support import ChatSessionResponse, ChatMessageResponse

@router.post("/chat/initiate", response_model=ChatSessionResponse)
def initiate_live_chat(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Start a live chat or automated chat session"""
    from app.services.support_service import SupportService
    session = SupportService.initiate_chat(db, current_user.id)
    return session

@router.post("/chat/{sessionId}/message", response_model=ChatMessageResponse)
def send_chat_message(
    sessionId: int,
    message: str = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Send a message in chat"""
    from app.models.support import ChatSession
    session = db.get(ChatSession, sessionId)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    from app.services.support_service import SupportService
    msg = SupportService.add_chat_message(db, sessionId, current_user.id, message)
    return msg

@router.get("/chat/{sessionId}/history", response_model=List[ChatMessageResponse])
def get_chat_history(
    sessionId: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Fetch full chat transcript"""
    from app.models.support import ChatSession, ChatMessage
    session = db.get(ChatSession, sessionId)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    return session.messages

@router.post("/tickets/{ticket_id}/attachment")
async def upload_ticket_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Upload attachment to support ticket"""
    # Get ticket
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Save file
    os.makedirs("uploads/support", exist_ok=True)
    file_name = f"ticket_{ticket_id}_{file.filename}"
    file_path = f"uploads/support/{file_name}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {
        "message": "Attachment uploaded successfully",
        "file_path": f"/static/{file_path}",
        "file_name": file.filename
    }

@router.get("/faq/search")
async def search_faq(
    q: str,
    db: Session = Depends(get_session)
):
    """Search FAQ by keyword"""
    statement = select(FAQ).where(
        (FAQ.question.contains(q)) |
        (FAQ.answer.contains(q))
    )
    results = db.exec(statement).all()
    
    return {
        "query": q,
        "results": results,
        "count": len(results)
    }
