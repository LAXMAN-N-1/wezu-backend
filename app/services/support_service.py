from sqlmodel import Session, select
from app.models.notification import Notification
from app.models.support import SupportTicket, ChatMessage
from app.schemas.support import SupportTicketCreate
from typing import List

class NotificationService:
    @staticmethod
    def get_user_notifications(db: Session, user_id: int) -> List[Notification]:
        return db.exec(select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())).all()

    @staticmethod
    def mark_read(db: Session, notification_id: int, user_id: int):
        notif = db.get(Notification, notification_id)
        if notif and notif.user_id == user_id:
            notif.is_read = True
            db.add(notif)
            db.commit()

class SupportService:
    @staticmethod
    def create_ticket(db: Session, user_id: int, ticket_in: SupportTicketCreate) -> SupportTicket:
        # Create ticket
        ticket = SupportTicket(
            user_id=user_id,
            subject=ticket_in.subject,
            priority=ticket_in.priority
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        
        # Create initial message
        msg = SupportMessage(
            ticket_id=ticket.id,
            sender_id=user_id,
            detail=ticket_in.detail
        )
        db.add(msg)
        db.commit()
        
        return ticket

    @staticmethod
    def get_tickets(db: Session, user_id: int) -> List[SupportTicket]:
        return db.exec(select(SupportTicket).where(SupportTicket.user_id == user_id).order_by(SupportTicket.updated_at.desc())).all()

    @staticmethod
    def add_message(db: Session, ticket_id: int, user_id: int, detail: str) -> ChatMessage:
        msg = SupportMessage(
            ticket_id=ticket_id,
            sender_id=user_id,
            detail=detail
        )
        db.add(msg)
        # Update ticket updated_at
        ticket = db.get(SupportTicket, ticket_id)
        if ticket:
             from datetime import datetime
             ticket.updated_at = datetime.utcnow()
             db.add(ticket)
             
        db.commit()
        db.refresh(msg)
        return msg
        
    @staticmethod
    def get_messages(db: Session, ticket_id: int) -> List[ChatMessage]:
        return db.exec(select(SupportMessage).where(SupportMessage.ticket_id == ticket_id).order_by(SupportMessage.created_at)).all()
