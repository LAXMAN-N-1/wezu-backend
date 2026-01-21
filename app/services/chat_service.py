"""
Chat Service
Live chat and automated responses
"""
from sqlmodel import Session, select
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.models.support import ChatSession, ChatMessage, AutoResponse
import logging

logger = logging.getLogger(__name__)

class ChatService:
    """Chat management service"""
    
    @staticmethod
    def create_session(user_id: int, session: Session) -> ChatSession:
        """Create new chat session"""
        chat_session = ChatSession(
            user_id=user_id,
            status="ACTIVE",
            started_at=datetime.utcnow()
        )
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        
        # Send welcome message
        ChatService.send_bot_message(
            chat_session.id,
            "Hello! How can I help you today?",
            session
        )
        
        return chat_session
    
    @staticmethod
    def send_message(
        session_id: int,
        sender_type: str,
        sender_id: Optional[int],
        message: str,
        session: Session
    ) -> ChatMessage:
        """Send chat message"""
        chat_message = ChatMessage(
            session_id=session_id,
            sender_type=sender_type,
            sender_id=sender_id,
            message=message,
            timestamp=datetime.utcnow()
        )
        session.add(chat_message)
        
        # Update session last message time
        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            chat_session.last_message_at = datetime.utcnow()
            session.add(chat_session)
        
        session.commit()
        session.refresh(chat_message)
        
        # Check for auto-response if customer message
        if sender_type == "CUSTOMER":
            auto_response = ChatService.get_auto_response(message, session)
            if auto_response:
                ChatService.send_bot_message(session_id, auto_response, session)
        
        return chat_message
    
    @staticmethod
    def send_bot_message(session_id: int, message: str, session: Session) -> ChatMessage:
        """Send automated bot message"""
        return ChatService.send_message(
            session_id=session_id,
            sender_type="BOT",
            sender_id=None,
            message=message,
            session=session
        )
    
    @staticmethod
    def get_auto_response(message: str, session: Session) -> Optional[str]:
        """Get automated response based on keywords"""
        message_lower = message.lower()
        
        # Get all active auto responses
        responses = session.exec(
            select(AutoResponse).where(AutoResponse.is_active == True)
        ).all()
        
        for response in responses:
            keywords = [k.strip().lower() for k in response.keywords.split(',')]
            if any(keyword in message_lower for keyword in keywords):
                # Update usage count
                response.usage_count += 1
                session.add(response)
                session.commit()
                return response.response_text
        
        return None
    
    @staticmethod
    def get_session_messages(session_id: int, limit: int, session: Session) -> List[ChatMessage]:
        """Get messages for chat session"""
        return session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.timestamp.desc())
            .limit(limit)
        ).all()
    
    @staticmethod
    def close_session(session_id: int, satisfaction: Optional[int], session: Session) -> bool:
        """Close chat session"""
        try:
            chat_session = session.get(ChatSession, session_id)
            if not chat_session:
                return False
            
            chat_session.status = "CLOSED"
            chat_session.closed_at = datetime.utcnow()
            chat_session.customer_satisfaction = satisfaction
            
            # Calculate resolution time
            if chat_session.started_at:
                resolution_time = (datetime.utcnow() - chat_session.started_at).total_seconds() / 60
                chat_session.resolution_time_minutes = int(resolution_time)
            
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
        return session.exec(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .where(ChatSession.status.in_(["ACTIVE", "WAITING"]))
            .order_by(ChatSession.started_at.desc())
        ).all()
    
    @staticmethod
    def mark_messages_read(session_id: int, session: Session):
        """Mark all messages in session as read"""
        messages = session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.is_read == False)
        ).all()
        
        for message in messages:
            message.is_read = True
            session.add(message)
        
        session.commit()
