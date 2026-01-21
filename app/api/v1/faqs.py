from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from typing import List
from app.api import deps
from app.models.faq import FAQ

router = APIRouter()

@router.get("/", response_model=List[FAQ])
async def get_faqs(
    category: str = None,
    db: Session = Depends(deps.get_db),
):
    query = select(FAQ).where(FAQ.is_active == True)
    if category:
        query = query.where(FAQ.category == category)
    return db.exec(query).all()
