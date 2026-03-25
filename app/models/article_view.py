from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.knowledge_article import KnowledgeArticle


class ArticleView(SQLModel, table=True):
    """Tracks individual view events for knowledge-base articles."""

    __tablename__ = "article_views"
    # __table_args__ = {"schema": "core"}

    id: Optional[int] = Field(default=None, primary_key=True)
    article_id: int = Field(foreign_key="knowledge_articles.id", index=True)
    user_id: Optional[int] = Field(
        default=None, foreign_key="users.id", index=True
    )
    ip_address: Optional[str] = Field(default=None, max_length=45)
    viewed_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    article: Optional["KnowledgeArticle"] = Relationship(back_populates="views")
