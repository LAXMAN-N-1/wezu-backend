"""
Chat Service
Live chat and automated responses

Model reality:
  ChatSession:  id, user_id, assigned_agent_id, status (ChatStatus: active/closed/waiting), created_at, updated_at
  ChatMessage:  id, session_id, sender_id (int, 0=bot), message, created_at
  AutoResponse: id, keyword (str), response (str), is_active, created_at
"""
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime, UTC
from app.models.support import ChatSession, ChatMessage, ChatStatus, AutoResponse
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """Chat management service"""

    @staticmethod
    def create_session(user_id: int, session: Session) -> ChatSession:
        """Create new chat session"""
        chat_session = ChatSession(
            user_id=user_id,
            status=ChatStatus.ACTIVE,
        )
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)

        # Send welcome message
        ChatService.send_bot_message(
            chat_session.id,
            "Hello! How can I help you today?",
            session,
        )

        return chat_session

    @staticmethod
    def send_message(
        session_id: int,
        sender_id: int,
        message: str,
        session: Session,
    ) -> ChatMessage:
        """Send chat message.  sender_id=0 for system/bot."""
        chat_message = ChatMessage(
            session_id=session_id,
            sender_id=sender_id,
            message=message,
        )
        session.add(chat_message)

        # Touch session updated_at
        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            chat_session.updated_at = datetime.now(UTC)
            session.add(chat_session)

        session.commit()
        session.refresh(chat_message)

        # Check for auto-response if customer message (non-bot)
        if sender_id != 0:
            auto_response = ChatService.get_auto_response(message, session)
            if auto_response:
                ChatService.send_bot_message(session_id, auto_response, session)

        return chat_message

    @staticmethod
    def send_bot_message(session_id: int, message: str, session: Session) -> ChatMessage:
        """Send automated bot message (sender_id=0)."""
        return ChatService.send_message(
            session_id=session_id,
            sender_id=0,
            message=message,
            session=session,
        )

    @staticmethod
    def get_auto_response(message: str, session: Session) -> Optional[str]:
        """Get automated response based on keyword matching."""
        message_lower = message.lower()

        responses = session.exec(
            select(AutoResponse).where(AutoResponse.is_active == True)  # noqa: E712
        ).all()

        for resp in responses:
            # AutoResponse.keyword is a single string; treat as comma-separated list
            keywords = [k.strip().lower() for k in (resp.keyword or "").split(",")]
            if any(kw and kw in message_lower for kw in keywords):
                return resp.response

        return None

    @staticmethod
    def get_session_messages(session_id: int, limit: int, session: Session) -> List[ChatMessage]:
        """Get messages for chat session, newest first."""
        return session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        ).all()

    @staticmethod
    def close_session(session_id: int, session: Session) -> bool:
        """Close chat session."""
        try:
            chat_session = session.get(ChatSession, session_id)
            if not chat_session:
                return False

            chat_session.status = ChatStatus.CLOSED
            chat_session.updated_at = datetime.now(UTC)

            session.add(chat_session)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error("Failed to close chat session: %s", e)
            return False

    @staticmethod
    def get_active_sessions(user_id: int, session: Session) -> List[ChatSession]:
        """Get active/waiting chat sessions for user."""
        return session.exec(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .where(ChatSession.status.in_([ChatStatus.ACTIVE, ChatStatus.WAITING]))
            .order_by(ChatSession.created_at.desc())
        ).all()
