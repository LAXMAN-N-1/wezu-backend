from __future__ import annotations
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from app.api import deps

from app.models.user import User
from app.schemas.review import ReviewResponse
from app.services.review_service import ReviewService

router = APIRouter()

@router.get("/", response_model=List[ReviewResponse])
def list_reviews_for_moderation(
    status: Optional[str] = Query(None, enum=["pending", "approved", "rejected"]),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
) -> Any:
    """Admin: all reviews with moderation controls"""
    return ReviewService.list_reviews_admin(db, skip, limit)

@router.put("/{id}/hide", response_model=ReviewResponse)
def hide_review(
    id: int,
    is_hidden: bool = True,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
) -> Any:
    """Admin: hide an inappropriate review"""
    return ReviewService.toggle_review_visibility(db, id, is_hidden)

@router.delete("/{id}")
def admin_delete_review(
    id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
    db: Session = Depends(deps.get_db),
) -> Any:
    """Admin: delete any review (hard delete)"""
    ReviewService.delete_review(db, id, current_user.id, is_admin=True)
    return {"status": "success", "message": "Review deleted by admin"}
