from sqlmodel import Session, select
from app.models.support import SupportTicket, TicketMessage
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
    def handle_new_ticket_message(db: Session, ticket_id: int, sender_id: int, message_text: str):
        """
        Add a message to a ticket and check for automated response.
        """
        # 1. Add User Message
        user_msg = TicketMessage(
            ticket_id=ticket_id,
            sender_id=sender_id,
            message=message_text
        )
        db.add(user_msg)
        db.commit()
        
        # 2. Check for Automated Response
        auto_reply = SupportService.get_automated_response(message_text)
        if auto_reply:
            # Find a system user or represent as 'Bot'
            # For now, we'll assume a system user or use a magic ID
            system_msg = TicketMessage(
                ticket_id=ticket_id,
                sender_id=0, # Representing System/Bot
                message=f"[Auto-Response] {auto_reply}"
            )
            db.add(system_msg)
            db.commit()
            return auto_reply
            
        return None
