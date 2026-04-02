from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, status
from sqlmodel import Session, select
from sqlalchemy import func
from app.api.deps import get_current_user
from app.api import deps
from app.models.user import User
from app.models.support import SupportTicket, TicketMessage
from app.models.feedback import Feedback
from app.models.faq import FAQ
from app.schemas.support import (
    TicketCreate, TicketMessageCreate, 
    SupportTicketResponse, SupportTicketDetailResponse
)
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.schemas.faq import FAQResponse
from datetime import datetime, UTC
import os
import shutil

router = APIRouter()

from app.schemas.common import PaginatedResponse, PaginationParams

@router.get("/admin/tickets", response_model=PaginatedResponse[SupportTicketResponse])
def admin_read_tickets(
    status: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: list all support tickets with pagination and filters"""
    statement = select(SupportTicket)
    if status:
        statement = statement.where(SupportTicket.status == status)
    if category:
        statement = statement.where(SupportTicket.category == category)
    
    # Get total count
    total = session.exec(select(func.count()).select_from(statement.subquery())).one()
    
    # Get paginated data
    offset = (page - 1) * limit
    tickets = session.exec(statement.order_by(SupportTicket.created_at.desc()).offset(offset).limit(limit)).all()
    
    return PaginatedResponse(
        data=tickets,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit
    )

@router.post("/tickets", response_model=SupportTicketResponse)
def create_ticket(
    *,
    session: Session = Depends(deps.get_db),
    ticket_in: TicketCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Customer: raise a new support ticket"""
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=ticket_in.subject,
        category=ticket_in.category,
        priority=ticket_in.priority,
        created_at=datetime.now(UTC)
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

@router.get("/tickets/my", response_model=PaginatedResponse[SupportTicketResponse])
def read_my_tickets(
    page: int = 1,
    limit: int = 10,
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Customer: list their own tickets with pagination"""
    statement = select(SupportTicket).where(SupportTicket.user_id == current_user.id)
    total = session.exec(select(func.count()).select_from(statement.subquery())).one()
    
    offset = (page - 1) * limit
    tickets = session.exec(statement.order_by(SupportTicket.created_at.desc()).offset(offset).limit(limit)).all()
    
    return PaginatedResponse(
        data=tickets,
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit
    )

@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetailResponse)
def read_ticket_detail(
    *,
    session: Session = Depends(deps.get_db),
    ticket_id: int,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get detailed thread."""
    ticket = session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    if ticket.user_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not permitted")
         
    return ticket

@router.post("/tickets/{ticket_id}/reply", response_model=SupportTicketDetailResponse)
def reply_ticket(
    *,
    session: Session = Depends(deps.get_db),
    ticket_id: int,
    reply_in: TicketMessageCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Add a response to the ticket."""
    ticket = session.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    from app.services.support_service import SupportService
    SupportService.handle_new_ticket_message(
        db=session,
        ticket_id=ticket.id,
        sender_id=current_user.id,
        message_text=reply_in.message
    )
    
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
    db: Session = Depends(deps.get_db)
):
    """Customer: close a resolved ticket"""
    from app.models.support import TicketStatus
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.status = TicketStatus.CLOSED
    ticket.updated_at = datetime.now(UTC)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket

# --- Live Chat ---
from app.schemas.support import ChatSessionResponse, ChatMessageResponse

@router.post("/chat/initiate", response_model=ChatSessionResponse)
def initiate_live_chat(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(deps.get_db)
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
    db: Session = Depends(deps.get_db)
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
    db: Session = Depends(deps.get_db)
):
    """Fetch full chat transcript"""
    from app.models.support import ChatSession
    session = db.get(ChatSession, sessionId)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat session not found")
        
    return session.messages

@router.post("/tickets/{ticket_id}/attachment")
async def upload_ticket_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Upload attachment to support ticket"""
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
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

# --- Admin Analytics ---
from app.schemas.support import QueueStatsResponse, AgentPerformanceResponse

@router.get("/admin/support/queue", response_model=QueueStatsResponse)
def get_support_queue_stats(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Admin: Overview of support ticket queue performance"""
    from app.services.support_service import SupportService
    return SupportService.get_queue_stats(session)

@router.get("/admin/support/performance", response_model=List[AgentPerformanceResponse])
def get_support_agent_performance(
    session: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """Admin: KPIs for all support agents"""
    from app.services.support_service import SupportService
    return SupportService.get_agent_performance(session)

# --- Feedback & FAQ (Knowledge Base) ---
@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    feedback_in: FeedbackCreate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """Submit app feedback"""
    feedback = Feedback(
        user_id=current_user.id,
        rating=feedback_in.rating,
        comment=feedback_in.comment,
        category=feedback_in.category,
        metadata=feedback_in.metadata
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback

@router.get("/feedback/my", response_model=List[FeedbackResponse])
async def list_my_feedback(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """List own feedback"""
    statement = select(Feedback).where(Feedback.user_id == current_user.id)
    return db.exec(statement).all()

@router.get("/faq", response_model=List[FAQResponse])
async def list_faqs(
    category: Optional[str] = None,
    db: Session = Depends(deps.get_db)
):
    """Knowledge Base: List FAQs with optional category filter"""
    from app.api.v1.faqs import get_faqs
    return await get_faqs(category, db)

@router.get("/faq/search")
async def search_faq(
    q: str,
    db: Session = Depends(deps.get_db)
):
    """Knowledge Base: Search FAQ by keyword"""
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

@router.get("/faq/{faq_id}", response_model=FAQResponse)
async def get_faq_detail(
    faq_id: int,
    db: Session = Depends(deps.get_db)
):
    """Knowledge Base: Get article detail"""
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return faq
