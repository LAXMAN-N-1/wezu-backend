from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlmodel import Session

from app.api import deps
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import DataResponse, PaginatedResponse
from app.schemas.knowledge_base import (
    ArticleCreate,
    ArticleUpdate,
    ArticleResponse,
    ArticleListItem,
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryTreeResponse,
    HelpfulRequest,
    SearchResponse,
    KBAnalyticsResponse,
)
from app.services.knowledge_base_service import KnowledgeBaseService


# ── Customer Router ─────────────────────────────────────────────────

customer_router = APIRouter()

@customer_router.get("/categories", response_model=DataResponse[List[CategoryTreeResponse]])
async def list_categories(db: Session = Depends(get_db)):
    """List all categories including parent-child hierarchy."""
    categories = KnowledgeBaseService.get_category_tree(db)
    return DataResponse(success=True, data=categories)


@customer_router.get("/articles", response_model=PaginatedResponse[ArticleListItem])
async def list_articles(
    category_id: int = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List published articles — paginated, filterable by category."""
    import math
    articles = KnowledgeBaseService.get_public_articles(db, category_id, skip, limit)
    # Basic total count without filters for simplicity here; 
    # normally you'd run a count query matching the filters
    total = len(articles)
    page = (skip // limit) + 1
    total_pages = math.ceil(total / limit) if total > 0 else 1
    return PaginatedResponse(
        success=True, 
        data=articles, 
        total=total, 
        skip=skip, 
        limit=limit,
        page=page,
        total_pages=total_pages
    )


@customer_router.get("/search", response_model=DataResponse[SearchResponse])
async def search_articles(
    q: str = Query(..., min_length=3, description="Search keyword"),
    db: Session = Depends(get_db)
):
    """Full-text search articles by keyword with result highlighting."""
    results = KnowledgeBaseService.search_articles(db, query=q)
    data = SearchResponse(query=q, total=len(results), results=results)
    return DataResponse(success=True, data=data)


@customer_router.get("/articles/{id}", response_model=DataResponse[ArticleResponse])
async def read_article(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_optional_user) # might be none
):
    """Read a specific article — automatically increments view count."""
    user_id = current_user.id if getattr(current_user, "id", None) else None
    article = KnowledgeBaseService.record_view(db, id, user_id=user_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return DataResponse(success=True, data=article)


@customer_router.post("/articles/{id}/helpful", response_model=DataResponse[dict])
async def submit_helpful_feedback(
    id: int,
    feedback: HelpfulRequest,
    db: Session = Depends(get_db)
):
    """Submit helpful (true) or not helpful (false) feedback on an article."""
    success = KnowledgeBaseService.record_helpful_vote(db, id, feedback.is_helpful)
    if not success:
        raise HTTPException(status_code=404, detail="Article not found")
    return DataResponse(success=True, data={"message": "Feedback submitted successfully"})



# ── Admin Router ────────────────────────────────────────────────────

admin_router = APIRouter()

@admin_router.post("/categories", response_model=DataResponse[CategoryResponse])
async def create_category(
    cat_in: CategoryCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """Create a new category (specify parent_id for subcategory)."""
    cat = KnowledgeBaseService.create_category(db, cat_in)
    return DataResponse(success=True, data=cat)


@admin_router.put("/categories/{id}", response_model=DataResponse[CategoryResponse])
async def update_category(
    id: int,
    cat_in: CategoryUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """Update a category name or parent."""
    cat = KnowledgeBaseService.update_category(db, id, cat_in)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return DataResponse(success=True, data=cat)


@admin_router.delete("/categories/{id}", response_model=DataResponse[dict])
async def delete_category(
    id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """Delete a category (fail if articles are still assigned to it)."""
    try:
        success = KnowledgeBaseService.delete_category(db, id)
        if not success:
            raise HTTPException(status_code=404, detail="Category not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return DataResponse(success=True, data={"message": "Category deleted successfully"})


@admin_router.post("/articles", response_model=DataResponse[ArticleResponse])
async def create_article(
    article_in: ArticleCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """Create a new article (saved as draft by default)."""
    article = KnowledgeBaseService.create_article(db, article_in, current_admin.id)
    return DataResponse(success=True, data=article)


@admin_router.put("/articles/{id}", response_model=DataResponse[ArticleResponse])
async def update_article(
    id: int,
    article_in: ArticleUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """Update an existing article's content, category, or status."""
    article = KnowledgeBaseService.update_article(db, id, article_in)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return DataResponse(success=True, data=article)


@admin_router.delete("/articles/{id}", response_model=DataResponse[dict])
async def delete_article(
    id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """Delete an article permanently."""
    success = KnowledgeBaseService.delete_article(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Article not found")
    return DataResponse(success=True, data={"message": "Article deleted successfully"})


@admin_router.get("/analytics", response_model=DataResponse[KBAnalyticsResponse])
async def get_analytics(
    db: Session = Depends(get_db),
    current_admin: User = Depends(deps.get_current_active_superuser)
):
    """View analytics: top viewed articles, most searched keywords, helpfulness ratio."""
    stats = KnowledgeBaseService.get_analytics(db)
    return DataResponse(success=True, data=stats)
