from sqlmodel import Session, select, func, or_, and_
from app.models.support import SupportTicket, TicketMessage, ChatSession, ChatMessage, ChatStatus, TicketStatus, TicketPriority
from app.models.user import User
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
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
    def handle_new_ticket_message(db: Session, ticket_id: int, sender_id: int, message_text: str, is_internal: bool = False, attachment_urls: List[str] = None):
        """Add a message to a ticket and check for automated response."""
        # 0. Check for Duplicate Message (identical content from same sender in this ticket)
        existing_msg = db.exec(
            select(TicketMessage).where(
                TicketMessage.ticket_id == ticket_id,
                TicketMessage.sender_id == sender_id,
                TicketMessage.message == message_text
            )
        ).first()
        
        if existing_msg:
             # Already exists
             return existing_msg, False

        # 1. Add User Message
        user_msg = TicketMessage(
            ticket_id=ticket_id,
            sender_id=sender_id,
            message=message_text,
            is_internal_note=is_internal,
            attachment_urls=attachment_urls or []
        )
        db.add(user_msg)
        
        # 2. Reopen if closed and not an internal note
        ticket = db.get(SupportTicket, ticket_id)
        if ticket and not is_internal and ticket.status == "closed":
             ticket.status = "open"
             db.add(ticket)
        
        db.commit()
        db.refresh(user_msg)
        
        # 3. Check for Automated Response (only for customer messages)
        if not is_internal:
            auto_reply = SupportService.get_automated_response(message_text)
            if auto_reply:
                auto_reply_text = f"[Auto-Response] {auto_reply}"
                
                # Check for duplicate auto-reply to avoid repeating it
                existing_auto = db.exec(
                    select(TicketMessage).where(
                        TicketMessage.ticket_id == ticket_id,
                        TicketMessage.sender_id == None,
                        TicketMessage.message == auto_reply_text
                    )
                ).first()
                
                if not existing_auto:
                    system_msg = TicketMessage(
                        ticket_id=ticket_id,
                        sender_id=None, # Representing System/Bot
                        message=auto_reply_text
                    )
                    db.add(system_msg)
                    db.commit()
                
        return user_msg, True

    @staticmethod
    def get_queue_stats(db: Session) -> dict:
        """Overview of the support queue"""
        from datetime import datetime, timedelta
        now = datetime.utcnow()
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
        from app.models.support import ChatMessage
        
        # Check for duplicate
        existing = db.exec(
            select(ChatMessage).where(
                ChatMessage.session_id == session_id,
                ChatMessage.sender_id == sender_id,
                ChatMessage.message == message
            )
        ).first()
        
        if existing:
            return existing

        msg = ChatMessage(session_id=session_id, sender_id=sender_id, message=message)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    @staticmethod
    def get_dealer_ticket_metrics(db: Session, dealer_id: int) -> dict:
        """Calculate and return support ticket metrics for a specific dealer"""
        now = datetime.utcnow()
        
        # 1. Total Open (open + in_progress)
        total_open = db.exec(
            select(func.count(SupportTicket.id))
            .where(
                SupportTicket.user_id == dealer_id,
                SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
            )
        ).one() or 0

        # 2. Avg Resolution Time (in hours)
        # We look at tickets that have been resolved or closed
        resolution_query = select(SupportTicket).where(
            SupportTicket.user_id == dealer_id,
            SupportTicket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED]),
            SupportTicket.resolved_at.is_not(None)
        )
        resolved_tickets = db.exec(resolution_query).all()
        
        avg_resolution_time = 0.0
        if resolved_tickets:
            total_duration_hours = sum(
                (t.resolved_at - t.created_at).total_seconds() / 3600 
                for t in resolved_tickets
            )
            avg_resolution_time = total_duration_hours / len(resolved_tickets)

        # 3. SLA Breach Count
        # SLA Definitions (hours): Critical: 4, High: 8, Medium: 24, Low: 48
        sla_thresholds = {
            TicketPriority.CRITICAL: 4,
            TicketPriority.HIGH: 8,
            TicketPriority.MEDIUM: 24,
            TicketPriority.LOW: 48
        }
        
        sla_breach_count = 0
        # Check active tickets
        active_tickets = db.exec(
            select(SupportTicket).where(
                SupportTicket.user_id == dealer_id,
                SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
            )
        ).all()
        
        for ticket in active_tickets:
            threshold = sla_thresholds.get(ticket.priority, 24)
            if (now - ticket.created_at).total_seconds() / 3600 > threshold:
                sla_breach_count += 1

        # 4. CSAT (Avg Rating)
        avg_csat = db.exec(
            select(func.avg(SupportTicket.rating))
            .where(
                SupportTicket.user_id == dealer_id,
                SupportTicket.rating.is_not(None)
            )
        ).one() or 0.0

        # 5. Category Breakdown
        category_query = db.exec(
            select(SupportTicket.category, func.count(SupportTicket.id))
            .where(SupportTicket.user_id == dealer_id)
            .group_by(SupportTicket.category)
        ).all()
        
        category_breakdown = [
            {"category": cat, "count": count} for cat, count in category_query
        ]

        return {
            "total_open": total_open,
            "avg_resolution_time": round(avg_resolution_time, 2),
            "sla_breach_count": sla_breach_count,
            "csat": round(float(avg_csat), 2),
            "category_breakdown": category_breakdown
        }

    @staticmethod
    def rate_ticket(db: Session, ticket_id: int, dealer_id: int, rating: int) -> SupportTicket:
        """Allow a dealer to rate a resolved or closed ticket"""
        ticket = db.get(SupportTicket, ticket_id)
        if not ticket:
            return None
        
        if ticket.user_id != dealer_id:
            raise ValueError("Unauthorized: You can only rate your own tickets")
            
        if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            raise ValueError("Invalid State: You can only rate a resolved or closed ticket")
            
        ticket.rating = rating
        ticket.rated_at = datetime.utcnow()
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket

    @staticmethod
    def update_ticket_action(db: Session, ticket_id: int, dealer_id: int, action_in: Any) -> SupportTicket:
        """Update ticket status, priority or escalate with a system message"""
        ticket = db.get(SupportTicket, ticket_id)
        if not ticket:
            return None
        
        if ticket.user_id != dealer_id:
            raise ValueError("Unauthorized: You can only update your own tickets")

        # 1. Handle Escalation
        if action_in.escalate:
            ticket.priority = TicketPriority.CRITICAL
            escalation_msg = f"[SYSTEM] Ticket escalated by dealer."
            if action_in.reason:
                escalation_msg += f" Reason: {action_in.reason}"
            
            # Add system message to the thread
            system_msg = TicketMessage(
                ticket_id=ticket.id,
                sender_id=None, # System
                message=escalation_msg
            )
            db.add(system_msg)

        # 2. Update Status/Priority if provided
        if action_in.status:
            ticket.status = action_in.status
            if action_in.status == TicketStatus.RESOLVED:
                ticket.resolved_at = datetime.utcnow()
        
        if action_in.priority and not action_in.escalate:
            ticket.priority = action_in.priority

        ticket.updated_at = datetime.utcnow()
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket
