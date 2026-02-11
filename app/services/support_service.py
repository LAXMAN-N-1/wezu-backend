from sqlmodel import Session, select
from app.models.support import SupportTicket, TicketMessage
from app.schemas.support import SupportTicketCreate
from typing import List
from datetime import datetime

class SupportService:
    @staticmethod
    def create_ticket(db: Session, user_id: int, ticket_in: SupportTicketCreate) -> SupportTicket:
        # Create ticket
        ticket = SupportTicket(
            user_id=user_id,
            subject=ticket_in.subject,
            category=getattr(ticket_in, "category", "general"),
            priority=ticket_in.priority
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        
        # Create initial message
        msg = TicketMessage(
            ticket_id=ticket.id,
            sender_id=user_id,
            message=ticket_in.detail
        )
        db.add(msg)
        db.commit()
        
        return ticket

    @staticmethod
    def get_tickets(db: Session, user_id: int) -> List[SupportTicket]:
        return db.exec(select(SupportTicket).where(SupportTicket.user_id == user_id).order_by(SupportTicket.updated_at.desc())).all()

    @staticmethod
    def add_message(db: Session, ticket_id: int, user_id: int, message_text: str) -> TicketMessage:
        msg = TicketMessage(
            ticket_id=ticket_id,
            sender_id=user_id,
            message=message_text
        )
        db.add(msg)
        # Update ticket updated_at
        ticket = db.get(SupportTicket, ticket_id)
        if ticket:
             ticket.updated_at = datetime.utcnow()
             db.add(ticket)
             
        db.commit()
        db.refresh(msg)
        return msg
        
    @staticmethod
    def get_messages(db: Session, ticket_id: int) -> List[TicketMessage]:
        return db.exec(select(TicketMessage).where(TicketMessage.ticket_id == ticket_id).order_by(TicketMessage.created_at)).all()

