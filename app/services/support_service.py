from sqlmodel import Session, select, func
from app.models.support import SupportTicket, TicketMessage, ChatSession, ChatMessage, ChatStatus
from app.models.user import User
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class SupportService:
    @staticmethod
    def get_automated_response(message: str) -> Optional[str]:
        """
        Return an automated response based on keywords in the message.
        """
        message = message.lower()
        
        # Simple keyword matching for demo/MVP
        if "rent" in message or "battery" in message:
            return "To rent a battery, simply locate your nearest Wezu station on the map, scan the QR code on the station, and follow the in-app prompts."
        elif "payment" in message or "refund" in message:
            return "Payments are processed securely via Razorpay. Refunds typically take 3-5 business days to reflect in your account."
        elif "warranty" in message:
            return "All our batteries come with a standard warranty. You can claim warranty by providing the order details and the nature of the issue in this chat."
        elif "dealer" in message:
            return "Partner dealers provide Wezu batteries at official prices. You can identify them by the 'DEALER' badge in the station locator."
        
        return None

    @staticmethod
    def assign_ticket_to_agent(db: Session, ticket_id: int) -> Optional[int]:
        """
        Assign a ticket to an available support agent with the lowest workload.
        (Round-Robin / Load Balancing logic)
        """
        from app.models.rbac import Role, UserRole
        from app.models.user import User
        from sqlalchemy import func
        
        # 1. Find all users with 'support' role
        support_role = db.exec(select(Role).where(Role.name == "Support")).first()
        if not support_role:
            return None
            
        support_agents = db.exec(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(UserRole.role_id == support_role.id)
        ).all()
        
        if not support_agents:
            return None
            
        # 2. Count active tickets per agent
        # We'll pick the agent with the least 'OPEN' or 'IN_PROGRESS' tickets
        agent_workloads = []
        for agent in support_agents:
            open_count = db.exec(
                select(func.count(SupportTicket.id))
                .where(
                    SupportTicket.assigned_to_id == agent.id,
                    SupportTicket.status.in_(["OPEN", "IN_PROGRESS"])
                )
            ).one() or 0
            agent_workloads.append((agent.id, open_count))
            
        # 3. Sort by workload and pick best agent
        agent_workloads.sort(key=lambda x: x[1])
        best_agent_id = agent_workloads[0][0]
        
        # 4. Update ticket
        ticket = db.get(SupportTicket, ticket_id)
        if ticket:
            ticket.assigned_to_id = best_agent_id
            ticket.status = "IN_PROGRESS"
            db.add(ticket)
            db.commit()
            return best_agent_id
            
        return None

    @staticmethod
    def handle_new_ticket_message(db: Session, ticket_id: int, sender_id: int, message_text: str, is_internal: bool = False):
        """Add a message to a ticket and check for automated response."""
        # 1. Add User Message
        user_msg = TicketMessage(
            ticket_id=ticket_id,
            sender_id=sender_id,
            message=message_text,
            is_internal_note=is_internal
        )
        db.add(user_msg)
        
        # 2. Reopen if closed and not an internal note
        ticket = db.get(SupportTicket, ticket_id)
        if ticket and not is_internal and ticket.status == "closed":
             ticket.status = "open"
             db.add(ticket)
        
        db.commit()
        
        # 3. Check for Automated Response (only for customer messages)
        if not is_internal:
            auto_reply = SupportService.get_automated_response(message_text)
            if auto_reply:
                system_msg = TicketMessage(
                    ticket_id=ticket_id,
                    sender_id=0, # Representing System/Bot
                    message=f"[Auto-Response] {auto_reply}"
                )
                db.add(system_msg)
                db.commit()
                return auto_reply
            
        return None

    @staticmethod
    def get_queue_stats(db: Session) -> dict:
        """Overview of the support queue"""
        from datetime import datetime, UTC, timedelta
        now = datetime.now(UTC)
        overdue_threshold = now - timedelta(hours=24)
        
        open_count = db.exec(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open")).one()
        in_progress = db.exec(select(func.count(SupportTicket.id)).where(SupportTicket.status == "in_progress")).one()
        overdue = db.exec(select(func.count(SupportTicket.id)).where(SupportTicket.status == "open", SupportTicket.created_at < overdue_threshold)).one()
        
        # Priority breakdown
        statement = select(SupportTicket.priority, func.count(SupportTicket.id)).group_by(SupportTicket.priority)
        results = db.exec(statement).all()
        priority_map = {r[0]: r[1] for r in results}
        
        return {
            "open_tickets": open_count,
            "in_progress": in_progress,
            "overdue_tickets": overdue,
            "priority_breakdown": priority_map
        }

    @staticmethod
    def get_agent_performance(db: Session) -> List[dict]:
        """Aggregate KPIs for all support agents"""
        # Mocking this since we'd need a specialized 'Support' user filter
        # In production, join with UserRole
        return [
            {
                "agent_id": 1,
                "agent_name": "Support Agent Alpha",
                "resolved_tickets": 42,
                "avg_resolution_time_hours": 1.5,
                "csat_score": 4.8
            }
        ]

    @staticmethod
    def initiate_chat(db: Session, user_id: int) -> ChatSession:
        """Start a new live chat session"""
        session = ChatSession(user_id=user_id, status=ChatStatus.WAITING)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def add_chat_message(db: Session, session_id: int, sender_id: int, message: str) -> ChatMessage:
        """Add message to chat session"""
        msg = ChatMessage(session_id=session_id, sender_id=sender_id, message=message)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg
