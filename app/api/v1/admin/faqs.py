from __future__ import annotations
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.api import deps
from app.api.deps import get_db
from app.models.user import User
from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQUpdate, FAQResponse
from datetime import datetime, timezone; UTC = timezone.utc

router = APIRouter()

@router.post("/", response_model=FAQResponse)
def create_faq(
    *,
    session: Session = Depends(get_db),
    faq_in: FAQCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: create a new FAQ article"""
    faq = FAQ.model_validate(faq_in)
    session.add(faq)
    session.commit()
    session.refresh(faq)
    return faq

@router.put("/{id}", response_model=FAQResponse)
def update_faq(
    *,
    session: Session = Depends(get_db),
    id: int,
    faq_in: FAQUpdate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: edit an existing FAQ article"""
    faq = session.get(FAQ, id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
        
    update_data = faq_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(faq, field, value)
    
    faq.updated_at = datetime.now(UTC)
    session.add(faq)
    session.commit()
    session.refresh(faq)
    return faq

@router.delete("/{id}", response_model=dict)
def delete_faq(
    *,
    session: Session = Depends(deps.get_db),
    id: int,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """Admin: delete or unpublish an FAQ article"""
    faq = session.get(FAQ, id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
        
    session.delete(faq)
    session.commit()
    return {"message": "FAQ deleted successfully"}
