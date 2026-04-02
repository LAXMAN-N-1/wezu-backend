from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, UTC

if TYPE_CHECKING:
    from app.models.user import User

class SecurityQuestion(SQLModel, table=True):
    __tablename__ = "security_questions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    question_text: str = Field(unique=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class UserSecurityQuestion(SQLModel, table=True):
    __tablename__ = "user_security_questions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    question_id: int = Field(foreign_key="security_questions.id")
    hashed_answer: str
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Relationships
    question: SecurityQuestion = Relationship()
