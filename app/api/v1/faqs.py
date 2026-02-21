from app.api import deps
from app.models.faq import FAQ
from app.schemas.faq import FAQResponse, FAQCategoryResponse

@router.get("/", response_model=List[FAQResponse])
async def get_faqs(
    category: str = None,
    q: str = None,
    db: Session = Depends(deps.get_db),
):
    """Public: list FAQ articles with category filter and keyword search"""
    query = select(FAQ).where(FAQ.is_active == True)
    if category:
        query = query.where(FAQ.category == category)
    if q:
        query = query.where(
            (FAQ.question.contains(q)) | (FAQ.answer.contains(q))
        )
    return db.exec(query).all()

@router.get("/categories", response_model=List[FAQCategoryResponse])
async def get_faq_categories(
    db: Session = Depends(deps.get_db),
):
    """List all FAQ categories"""
    from sqlmodel import func
    statement = select(FAQ.category, func.count(FAQ.id)).where(FAQ.is_active == True).group_by(FAQ.category)
    results = db.exec(statement).all()
    return [{"category": r[0], "count": r[1]} for r in results]

@router.get("/{id}", response_model=FAQResponse)
async def get_faq_detail(
    id: int,
    db: Session = Depends(deps.get_db),
):
    """Single FAQ article detail"""
    faq = db.get(FAQ, id)
    if not faq or not faq.is_active:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="FAQ not found")
    return faq

@router.post("/{id}/helpful", response_model=dict)
async def mark_faq_helpful(
    id: int,
    is_helpful: bool = True,
    db: Session = Depends(deps.get_db),
):
    """User: mark article as helpful or not (for analytics)"""
    faq = db.get(FAQ, id)
    if not faq:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    if is_helpful:
        faq.helpful_count += 1
    else:
        faq.not_helpful_count += 1
        
    db.add(faq)
    db.commit()
    return {"message": "Thank you for your feedback"}
