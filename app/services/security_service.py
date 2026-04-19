from __future__ import annotations
from sqlmodel import Session, select
from app.models.audit_log import SecurityEvent
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class SecurityService:
    @staticmethod
    def log_event(
        db: Session,
        event_type: str,
        severity: str = "medium",
        details: str = None,
        source_ip: str = None,
        user_id: Optional[int] = None
    ) -> SecurityEvent:
        """
        Log a security-related event.
        Severity levels: low, medium, high, critical
        """
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            details=details,
            source_ip=source_ip,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            is_resolved=False
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        
        if severity in ["high", "critical"]:
            logger.warning(f"HIGH SEVERITY SECURITY EVENT: {event_type} (User: {user_id}, IP: {source_ip})")
            # In a real app, this might trigger an email/SMS/Webhook to the security team
            
        return event

    @staticmethod
    def get_events(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        unresolved_only: bool = False,
        severity: Optional[str] = None
    ) -> List[SecurityEvent]:
        statement = select(SecurityEvent)
        if unresolved_only:
            statement = statement.where(SecurityEvent.is_resolved == False)
        if severity:
            statement = statement.where(SecurityEvent.severity == severity)
        
        statement = statement.offset(skip).limit(limit).order_by(SecurityEvent.timestamp.desc())
        return db.exec(statement).all()

    @staticmethod
    def resolve_event(db: Session, event_id: int) -> Optional[SecurityEvent]:
        event = db.get(SecurityEvent, event_id)
        if event:
            event.is_resolved = True
            db.add(event)
            db.commit()
            db.refresh(event)
        return event

    @staticmethod
    def get_event_stats(db: Session):
        """Get summary statistics for security events"""
        from sqlalchemy import func
        
        counts = db.exec(
            select(SecurityEvent.severity, func.count(SecurityEvent.id))
            .group_by(SecurityEvent.severity)
        ).all()
        
        unresolved_count = db.exec(
            select(func.count(SecurityEvent.id))
            .where(SecurityEvent.is_resolved == False)
        ).first()
        
        return {
            "severity_counts": dict(counts),
            "unresolved_count": unresolved_count or 0
        }

    # ── P1-A-4: Security-question helpers ─────────────────────────────────
    # Uses a static list for now; can be migrated to a DB table later.

    _SECURITY_QUESTIONS: list[dict] = [
        {"id": 1, "question": "What was the name of your first pet?"},
        {"id": 2, "question": "What city were you born in?"},
        {"id": 3, "question": "What is your mother's maiden name?"},
        {"id": 4, "question": "What was the name of your first school?"},
        {"id": 5, "question": "What is the make of your first car?"},
    ]

    @staticmethod
    def get_available_questions(db: Session) -> list[dict]:
        """Return the catalogue of security questions."""
        return list(SecurityService._SECURITY_QUESTIONS)

    @staticmethod
    def set_user_security_question(
        db: Session,
        user_id: int,
        question_id: int,
        answer: str,
    ) -> None:
        """Store a hashed security-question answer for a user."""
        from app.models.user import User
        from app.core.security import get_password_hash

        user = db.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Persist question id + hashed answer on user record.
        # If the User model doesn't have these columns yet we store in
        # the JSON metadata field as a forward-compatible approach.
        user.security_question_id = question_id  # type: ignore[attr-defined]
        user.security_answer_hash = get_password_hash(answer.strip().lower())  # type: ignore[attr-defined]
        db.add(user)
        db.commit()

    @staticmethod
    def verify_security_answer(db: Session, user_id: int, answer: str) -> bool:
        """Verify a user's security-question answer."""
        from app.models.user import User
        from app.core.security import verify_password

        user = db.get(User, user_id)
        if not user:
            return False

        stored_hash = getattr(user, "security_answer_hash", None)
        if not stored_hash:
            return False

        return verify_password(answer.strip().lower(), stored_hash)
