from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum
import sqlalchemy as sa


if TYPE_CHECKING:
    from app.models.article_category import ArticleCategory
    from app.models.article_view import ArticleView


class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class KnowledgeArticle(SQLModel, table=True):
    """Full knowledge-base article that replaces the legacy FAQ entry."""

    __tablename__ = "knowledge_articles"
    __table_args__ = {"schema": "core"}

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=200)
    slug: str = Field(max_length=220, unique=True, index=True)
    content: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    category_id: Optional[int] = Field(
        default=None, foreign_key="core.article_categories.id"
    )
    tags: Optional[List[str]] = Field(default=None, sa_column=sa.Column(sa.JSON))
    status: ArticleStatus = Field(default=ArticleStatus.DRAFT, index=True)
    author_id: Optional[int] = Field(
        default=None, foreign_key="core.users.id"
    )

    views_count: int = Field(default=0)
    helpful_count: int = Field(default=0)
    not_helpful_count: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = Field(default=None)

    # Relationships
    category: Optional["ArticleCategory"] = Relationship(back_populates="articles")
    views: List["ArticleView"] = Relationship(back_populates="article")
