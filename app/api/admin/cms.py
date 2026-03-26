from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from sqlmodel import Session, select
from typing import List, Any, Optional
from app.api import deps
from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQUpdate
from app.models.blog import Blog
from app.schemas.blog import BlogCreate, BlogUpdate, BlogPublic

router = APIRouter()

@router.post("/faqs/", response_model=FAQ, status_code=status.HTTP_201_CREATED)
async def create_faq(
    *,
    db: Session = Depends(deps.get_db),
    faq_in: FAQCreate,
) -> Any:
    """
    Create a new FAQ.
    """
    faq = FAQ.model_validate(faq_in)
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq

@router.put("/faqs/{faq_id}", response_model=FAQ)
async def update_faq(
    *,
    db: Session = Depends(deps.get_db),
    faq_id: int,
    faq_in: FAQUpdate,
) -> Any:
    """
    Update an existing FAQ.
    """
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    update_data = faq_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(faq, field, value)
        
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq

@router.delete("/faqs/{faq_id}", response_model=dict)
async def delete_faq(
    *,
    db: Session = Depends(deps.get_db),
    faq_id: int,
) -> Any:
    """
    Delete an FAQ.
    """
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
        
    db.delete(faq)
    db.commit()
    return {"message": "FAQ successfully deleted"}

# --- Blog Endpoints ---

@router.get("/blogs/", response_model=List[BlogPublic])
async def list_blogs(
    *,
    db: Session = Depends(deps.get_db),
    category: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve blogs.
    """
    query = select(Blog)
    if category:
        query = query.where(Blog.category == category)
    if status:
        query = query.where(Blog.status == status)
    
    query = query.offset(skip).limit(limit)
    blogs = db.exec(query).all()
    return blogs

@router.post("/blogs/", response_model=BlogPublic, status_code=status.HTTP_201_CREATED)
async def create_blog(
    *,
    db: Session = Depends(deps.get_db),
    blog_in: BlogCreate,
) -> Any:
    """
    Create a new blog.
    """
    blog = Blog.model_validate(blog_in)
    db.add(blog)
    db.commit()
    db.refresh(blog)
    return blog

@router.get("/blogs/{blog_id}", response_model=BlogPublic)
async def get_blog(
    *,
    db: Session = Depends(deps.get_db),
    blog_id: int,
) -> Any:
    """
    Get blog by ID.
    """
    blog = db.get(Blog, blog_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    return blog

@router.put("/blogs/{blog_id}", response_model=BlogPublic)
async def update_blog(
    *,
    db: Session = Depends(deps.get_db),
    blog_id: int,
    blog_in: BlogUpdate,
) -> Any:
    """
    Update a blog.
    """
    blog = db.get(Blog, blog_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    
    update_data = blog_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(blog, field, value)
        
    blog.updated_at = datetime.utcnow()
    db.add(blog)
    db.commit()
    db.refresh(blog)
    return blog

@router.delete("/blogs/{blog_id}", response_model=dict)
async def delete_blog(
    *,
    db: Session = Depends(deps.get_db),
    blog_id: int,
) -> Any:
    """
    Delete a blog.
    """
    blog = db.get(Blog, blog_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
        
    db.delete(blog)
    db.commit()
    return {"message": "Blog successfully deleted"}
