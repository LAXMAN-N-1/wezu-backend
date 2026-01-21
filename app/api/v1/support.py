"""
Support and Chat API
Live chat, tickets, and FAQ
"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional, List

from app.api import deps
from app.db.session import get_session
from app.models.user import User
from app.models.support import ChatSession, ChatMessage, SupportTicket, FAQItem, FAQCategory
from app.services.chat_service import ChatService
from app.services.websocket_service import manager
from app.schemas.common import DataResponse

router = APIRouter()

# Schemas
class SendMessageRequest(BaseModel):
    message: str
    attachment_url: Optional[str] = None

class CloseSessionRequest(BaseModel):
    satisfaction: Optional[int] = None

class CreateTicketRequest(BaseModel):
    subject: str
    description: str
    category: str
    priority: str = "MEDIUM"

# Chat Endpoints
@router.post("/chat/start", response_model=DataResponse[dict])
def start_chat(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Start new chat session"""
    # Check for existing active session
    active_sessions = ChatService.get_active_sessions(current_user.id, session)
    
    if active_sessions:
        chat_session = active_sessions[0]
    else:
        chat_session = ChatService.create_session(current_user.id, session)
    
    return DataResponse(
        success=True,
        data={
            "session_id": chat_session.id,
            "status": chat_session.status,
            "started_at": chat_session.started_at.isoformat()
        }
    )

@router.post("/chat/{session_id}/message", response_model=DataResponse[dict])
def send_message(
    session_id: int,
    request: SendMessageRequest,
    current_user: User = Depends(deps.get_current_user),
    db_session: Session = Depends(get_session)
):
    """Send message in chat"""
    # Verify session belongs to user
    chat_session = db_session.get(ChatSession, session_id)
    if not chat_session or chat_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    message = ChatService.send_message(
        session_id=session_id,
        sender_type="CUSTOMER",
        sender_id=current_user.id,
        message=request.message,
        session=db_session
    )
    
    return DataResponse(
        success=True,
        data={
            "message_id": message.id,
            "timestamp": message.timestamp.isoformat()
        }
    )

@router.get("/chat/{session_id}/messages", response_model=DataResponse[list])
def get_messages(
    session_id: int,
    limit: int = 50,
    current_user: User = Depends(deps.get_current_user),
    db_session: Session = Depends(get_session)
):
    """Get chat messages"""
    chat_session = db_session.get(ChatSession, session_id)
    if not chat_session or chat_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    messages = ChatService.get_session_messages(session_id, limit, db_session)
    
    return DataResponse(
        success=True,
        data=[
            {
                "id": msg.id,
                "sender_type": msg.sender_type,
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat(),
                "is_read": msg.is_read
            }
            for msg in reversed(messages)
        ]
    )

@router.post("/chat/{session_id}/close", response_model=DataResponse[dict])
def close_chat(
    session_id: int,
    request: CloseSessionRequest,
    current_user: User = Depends(deps.get_current_user),
    db_session: Session = Depends(get_session)
):
    """Close chat session"""
    chat_session = db_session.get(ChatSession, session_id)
    if not chat_session or chat_session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    success = ChatService.close_session(session_id, request.satisfaction, db_session)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to close session"
        )
    
    return DataResponse(
        success=True,
        data={"message": "Chat session closed successfully"}
    )

# Ticket Endpoints
@router.post("/tickets", response_model=DataResponse[dict])
def create_ticket(
    request: CreateTicketRequest,
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Create support ticket"""
    from datetime import datetime
    import uuid
    
    ticket_number = f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    ticket = SupportTicket(
        ticket_number=ticket_number,
        user_id=current_user.id,
        subject=request.subject,
        description=request.description,
        category=request.category,
        priority=request.priority,
        status="OPEN"
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    
    return DataResponse(
        success=True,
        data={
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "status": ticket.status
        }
    )

@router.get("/tickets", response_model=DataResponse[list])
def get_user_tickets(
    current_user: User = Depends(deps.get_current_user),
    session: Session = Depends(get_session)
):
    """Get all tickets for user"""
    tickets = session.exec(
        select(SupportTicket)
        .where(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.created_at.desc())
    ).all()
    
    return DataResponse(
        success=True,
        data=[
            {
                "id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "subject": ticket.subject,
                "category": ticket.category,
                "priority": ticket.priority,
                "status": ticket.status,
                "created_at": ticket.created_at.isoformat()
            }
            for ticket in tickets
        ]
    )

# FAQ Endpoints
@router.get("/faq", response_model=DataResponse[list])
def get_faq(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Get FAQ items"""
    query = select(FAQItem).where(FAQItem.is_active == True)
    
    if category_id:
        query = query.where(FAQItem.category_id == category_id)
    
    if search:
        query = query.where(
            FAQItem.question.ilike(f"%{search}%") | 
            FAQItem.answer.ilike(f"%{search}%")
        )
    
    query = query.order_by(FAQItem.display_order)
    
    items = session.exec(query).all()
    
    return DataResponse(
        success=True,
        data=[
            {
                "id": item.id,
                "question": item.question,
                "answer": item.answer,
                "helpful_count": item.helpful_count
            }
            for item in items
        ]
    )

@router.get("/faq/categories", response_model=DataResponse[list])
def get_faq_categories(session: Session = Depends(get_session)):
    """Get FAQ categories"""
    categories = session.exec(
        select(FAQCategory)
        .where(FAQCategory.is_active == True)
        .order_by(FAQCategory.display_order)
    ).all()
    
    return DataResponse(
        success=True,
        data=[
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description
            }
            for cat in categories
        ]
    )
