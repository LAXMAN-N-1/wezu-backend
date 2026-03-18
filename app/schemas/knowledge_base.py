"""
Pydantic schemas for Knowledge Base — articles, categories, search, analytics.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# ── Category Schemas ────────────────────────────────────────────────

class CategoryBase(BaseModel):
    name: str = Field(max_length=100)
    slug: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=500)
    parent_id: Optional[int] = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryResponse(CategoryBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CategoryTreeResponse(CategoryResponse):
    """Includes nested children for hierarchy display."""
    children: List["CategoryTreeResponse"] = []


# ── Article Schemas ─────────────────────────────────────────────────

class ArticleBase(BaseModel):
    title: str = Field(max_length=200)
    content: str
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None


class ArticleCreate(ArticleBase):
    status: str = "draft"


class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = None
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class ArticleResponse(ArticleBase):
    id: int
    slug: str
    status: str
    author_id: Optional[int] = None
    views_count: int
    helpful_count: int
    not_helpful_count: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ArticleListItem(BaseModel):
    id: int
    title: str
    slug: str
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    status: str
    views_count: int
    helpful_count: int
    not_helpful_count: int
    created_at: datetime
    published_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ── Helpful Feedback ────────────────────────────────────────────────

class HelpfulRequest(BaseModel):
    is_helpful: bool


# ── Search ──────────────────────────────────────────────────────────

class SearchResultItem(BaseModel):
    id: int
    title: str
    slug: str
    snippet: str  # highlighted excerpt
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    views_count: int


class SearchResponse(BaseModel):
    query: str
    total: int
    results: List[SearchResultItem]


# ── Admin Analytics ─────────────────────────────────────────────────

class TopArticle(BaseModel):
    id: int
    title: str
    views_count: int
    helpful_count: int
    not_helpful_count: int


class HelpfulnessRatio(BaseModel):
    id: int
    title: str
    helpful_count: int
    not_helpful_count: int
    ratio: float  # helpful / (helpful + not_helpful)


class KBAnalyticsResponse(BaseModel):
    total_articles: int
    total_published: int
    total_views: int
    top_viewed: List[TopArticle]
    most_helpful: List[HelpfulnessRatio]
    least_helpful: List[HelpfulnessRatio]
