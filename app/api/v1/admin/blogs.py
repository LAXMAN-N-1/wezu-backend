from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from app.db.session import get_session
from app.models.user import User
from app.models.blog import Blog
from app.schemas.blog import BlogCreate, BlogUpdate, BlogRead
from app.api.deps import get_current_active_admin
from datetime import datetime, UTC

router = APIRouter()

@router.get("/", response_model=List[BlogRead])
def read_blogs(
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    status: Optional[str] = None,
    admin: User = Depends(get_current_active_admin),
):
    query = select(Blog)
    if category:
        query = query.where(Blog.category == category)
    if status:
        query = query.where(Blog.status == status)
    
    blogs = session.exec(query.offset(offset).limit(limit)).all()
    return blogs

@router.post("/", response_model=BlogRead)
def create_blog(
    *,
    session: Session = Depends(get_session),
    blog_in: BlogCreate,
    admin: User = Depends(get_current_active_admin),
):
    db_blog = Blog.model_validate(blog_in)
    db_blog.author_id = admin.id
    if db_blog.status == "published":
        db_blog.published_at = datetime.now(UTC)
    
    session.add(db_blog)
    session.commit()
    session.refresh(db_blog)
    return db_blog

@router.get("/{blog_id}", response_model=BlogRead)
def read_blog(
    blog_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    blog = session.get(Blog, blog_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    return blog

@router.patch("/{blog_id}", response_model=BlogRead)
def update_blog(
    *,
    session: Session = Depends(get_session),
    blog_id: int,
    blog_in: BlogUpdate,
    admin: User = Depends(get_current_active_admin),
):
    db_blog = session.get(Blog, blog_id)
    if not db_blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    
    blog_data = blog_in.model_dump(exclude_unset=True)
    for key, value in blog_data.items():
        setattr(db_blog, key, value)
    
    if "status" in blog_data and blog_data["status"] == "published" and not db_blog.published_at:
        db_blog.published_at = datetime.now(UTC)
        
    db_blog.updated_at = datetime.now(UTC)
    session.add(db_blog)
    session.commit()
    session.refresh(db_blog)
    return db_blog

@router.delete("/{blog_id}")
def delete_blog(
    blog_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    blog = session.get(Blog, blog_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    session.delete(blog)
    session.commit()
    return {"ok": True}
