from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.knowledge_article import KnowledgeArticle


class ArticleCategory(SQLModel, table=True):
    """Hierarchical category for knowledge-base articles."""

    __tablename__ = "article_categories"
    # __table_args__ = {"schema": "core"}

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, index=True)
    slug: str = Field(max_length=120, unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=500)
    parent_id: Optional[int] = Field(
        default=None, foreign_key="article_categories.id"
    )
    sort_order: int = Field(default=0)
    is_active: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    parent: Optional["ArticleCategory"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "ArticleCategory.id"},
    )
    children: List["ArticleCategory"] = Relationship(back_populates="parent")
    articles: List["KnowledgeArticle"] = Relationship(back_populates="category")
