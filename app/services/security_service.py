from sqlmodel import Session, select
from app.models.user import User
from app.models.security_question import SecurityQuestion, UserSecurityQuestion
from app.core.security import get_password_hash, verify_password
from fastapi import HTTPException, status
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class SecurityService:
    @staticmethod
    def change_password(db: Session, user: User, current_password: str, new_password: str):
        """Verify current password and update to new password"""
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password"
            )
        
        user.hashed_password = get_password_hash(new_password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return True

    @staticmethod
    def get_available_questions(db: Session) -> List[SecurityQuestion]:
        """List all active security questions"""
        return db.exec(select(SecurityQuestion).where(SecurityQuestion.is_active == True)).all()

    @staticmethod
    def set_user_security_question(db: Session, user_id: int, question_id: int, answer: str):
        """Set or update user's security question"""
        # 1. Check if question exists
        question = db.get(SecurityQuestion, question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Security question not found")
        
        # 2. Check if already exists for user
        statement = select(UserSecurityQuestion).where(UserSecurityQuestion.user_id == user_id)
        user_sq = db.exec(statement).first()
        
        if not user_sq:
            user_sq = UserSecurityQuestion(user_id=user_id)
            
        user_sq.question_id = question_id
        # We hash the answer for security
        user_sq.hashed_answer = get_password_hash(answer.lower().strip())
        
        db.add(user_sq)
        db.commit()
        db.refresh(user_sq)
        return user_sq

    @staticmethod
    def verify_security_answer(db: Session, user_id: int, answer: str) -> bool:
        """Verify user's answer to their security question"""
        statement = select(UserSecurityQuestion).where(UserSecurityQuestion.user_id == user_id)
        user_sq = db.exec(statement).first()
        
        if not user_sq:
            raise HTTPException(status_code=400, detail="Security question not set for this user")
            
        return verify_password(answer.lower().strip(), user_sq.hashed_answer)
