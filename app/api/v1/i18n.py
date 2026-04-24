from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.models.i18n import Translation
from app.services.i18n_service import I18nService
from pydantic import BaseModel

router = APIRouter()

class TranslationUpdate(BaseModel):
    key: str
    lang: str
    value: str

@router.get("/{lang}", response_model=dict)
def get_translations(
    lang: str,
    db: Session = Depends(deps.get_db),
):
    """
    Get all translations for a language (key-value dict) for frontend caching.
    """
    ts = db.exec(select(Translation).where(Translation.language_code == lang)).all()
    result = {t.key: t.value for t in ts}
    return result

@router.post("/", response_model=dict)
def update_translation(
    t_in: TranslationUpdate,
    current_user: User = Depends(deps.check_permission("i18n", "edit")), # Admin only
):
    I18nService.set_translation(t_in.key, t_in.lang, t_in.value)
    return {"status": "updated"}
