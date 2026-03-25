from app.core.database import get_db
"""
Chat Service
Live chat and automated responses
"""
from sqlmodel import Session, select, col, desc
from typing import List, Dict, Optional
from datetime import datetime
from app.models.support import ChatSession, ChatMessage, ChatStatus
import logging

logger = logging.getLogger(__name__)

class ChatService:
    """Chat management service"""
    
    @staticmethod
    def create_session(user_id: int, session: Session) -> ChatSession:
        """Create new chat session"""
        chat_session = ChatSession(
            user_id=user_id,
            status=ChatStatus.ACTIVE
        )
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        
        # Send welcome message
        assert chat_session.id is not None
        ChatService.send_bot_message(
            chat_session.id,
            "Hello! How can I help you today?",
            session
        )
        
        return chat_session
    
    @staticmethod
    def send_message(
        session_id: int,
        sender_id: int,
        message: str,
        session: Session
    ) -> ChatMessage:
        """Send chat message"""
        chat_message = ChatMessage(
            session_id=session_id,
            sender_id=sender_id,
            message=message
        )
        session.add(chat_message)
        
        # Update session timestamp
        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            chat_session.updated_at = datetime.utcnow()
            session.add(chat_session)
        
        session.commit()
        session.refresh(chat_message)
        
        return chat_message
    
    @staticmethod
    def send_bot_message(session_id: int, message: str, session: Session) -> ChatMessage:
        """Send automated bot message"""
        return ChatService.send_message(
            session_id=session_id,
            sender_id=0, # 0 for BOT
            message=message,
            session=session
        )
    
    @staticmethod
    def get_auto_response(message: str, session: Session) -> Optional[str]:
        """Get automated response based on keywords (Stub)"""
        # AutoResponse model is missing, using simplified keyword matching logic
        # You could implement this via FAQ or another model if available
        return None
    
    @staticmethod
    def get_session_messages(session_id: int, limit: int, session: Session) -> List[ChatMessage]:
        """Get messages for chat session"""
        return list(session.exec(
            select(ChatMessage)
            .where(col(ChatMessage.session_id) == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        ).all())
    
    @staticmethod
    def close_session(session_id: int, session: Session) -> bool:
        """Close chat session"""
        try:
            chat_session = session.get(ChatSession, session_id)
            if not chat_session:
                return False
            
            chat_session.status = ChatStatus.CLOSED
            chat_session.updated_at = datetime.utcnow()
            
            session.add(chat_session)
            session.commit()
            
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to close chat session: {str(e)}")
            return False
    
    @staticmethod
    def get_active_sessions(user_id: int, session: Session) -> List[ChatSession]:
        """Get active chat sessions for user"""
        return list(session.exec(
            select(ChatSession)
            .where(col(ChatSession.user_id) == user_id)
            .where(col(ChatSession.status).in_([ChatStatus.ACTIVE, ChatStatus.WAITING]))
            .order_by(desc(ChatSession.created_at))
        ).all())
    
    @staticmethod
    def mark_messages_read(session_id: int, session: Session):
        """Mark all messages in session as read (Stub - is_read field missing in model)"""
        # ChatMessage model is missing is_read field. 
        # This is a placeholder for future implementation.
        pass
