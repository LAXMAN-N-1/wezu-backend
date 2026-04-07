"""Comprehensive CMS Admin API — Blogs, FAQs, Banners, Legal Docs, Media Assets."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, UTC
from sqlmodel import Session, select, func
from typing import List, Any, Optional
from app.core.database import get_db
from app.api.deps import get_current_active_admin
from app.models.user import User

# FAQ
from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQUpdate, FAQResponse

# Blog
from app.models.blog import Blog
from app.schemas.blog import BlogCreate, BlogUpdate, BlogPublic

# Banner
from app.models.banner import Banner
from app.schemas.banner import BannerCreate, BannerUpdate, BannerRead

# Legal
from app.models.legal import LegalDocument
from app.schemas.legal import LegalDocumentCreate, LegalDocumentUpdate, LegalDocumentRead

# Media
from app.models.media import MediaAsset
from app.schemas.media import MediaAssetRead, MediaAssetUpdate

router = APIRouter()

# ============================================================================
# FAQ Endpoints
# ============================================================================

@router.get("/faqs", include_in_schema=False)
@router.get("/faqs/", response_model=List[FAQResponse])
def list_faqs(
    db: Session = Depends(get_db),
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    query = select(FAQ)
    if category:
        query = query.where(FAQ.category == category)
    if is_active is not None:
        query = query.where(FAQ.is_active == is_active)
    faqs = db.exec(query.offset(skip).limit(limit)).all()
    return faqs

@router.post("/faqs/", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
def create_faq(
    *, db: Session = Depends(get_db), faq_in: FAQCreate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    faq = FAQ.model_validate(faq_in)
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq

@router.put("/faqs/{faq_id}", response_model=FAQResponse)
def update_faq(
    *, db: Session = Depends(get_db), faq_id: int, faq_in: FAQUpdate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    for field, value in faq_in.model_dump(exclude_unset=True).items():
        setattr(faq, field, value)
    faq.updated_at = datetime.now(UTC)
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq

@router.delete("/faqs/{faq_id}")
def delete_faq(
    faq_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    faq = db.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    db.delete(faq)
    db.commit()
    return {"message": "FAQ deleted successfully"}

# ============================================================================
# Blog Endpoints
# ============================================================================

@router.get("/blogs", include_in_schema=False)
@router.get("/blogs/", response_model=List[BlogPublic])
def list_blogs(
    *, db: Session = Depends(get_db),
    category: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0, limit: int = 100,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    query = select(Blog)
    if category:
        query = query.where(Blog.category == category)
    if status:
        query = query.where(Blog.status == status)
    return db.exec(query.order_by(Blog.created_at.desc()).offset(skip).limit(limit)).all()

@router.post("/blogs/", response_model=BlogPublic, status_code=status.HTTP_201_CREATED)
def create_blog(
    *, db: Session = Depends(get_db), blog_in: BlogCreate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    blog = Blog.model_validate(blog_in)
    db.add(blog)
    db.commit()
    db.refresh(blog)
    return blog

@router.get("/blogs/{blog_id}", response_model=BlogPublic)
def get_blog(
    blog_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    blog = db.get(Blog, blog_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    return blog

@router.put("/blogs/{blog_id}", response_model=BlogPublic)
def update_blog(
    *, db: Session = Depends(get_db), blog_id: int, blog_in: BlogUpdate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    blog = db.get(Blog, blog_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    for field, value in blog_in.model_dump(exclude_unset=True).items():
        setattr(blog, field, value)
    blog.updated_at = datetime.now(UTC)
    db.add(blog)
    db.commit()
    db.refresh(blog)
    return blog

@router.delete("/blogs/{blog_id}")
def delete_blog(
    blog_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    blog = db.get(Blog, blog_id)
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    db.delete(blog)
    db.commit()
    return {"message": "Blog deleted successfully"}

# ============================================================================
# Banner Endpoints
# ============================================================================

@router.get("/banners", include_in_schema=False)
@router.get("/banners/", response_model=List[BannerRead])
def list_banners(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    return db.exec(select(Banner).order_by(Banner.priority.desc())).all()

@router.post("/banners/", response_model=BannerRead, status_code=status.HTTP_201_CREATED)
def create_banner(
    *, db: Session = Depends(get_db), banner_in: BannerCreate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    banner = Banner.model_validate(banner_in)
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return banner

@router.patch("/banners/{banner_id}", response_model=BannerRead)
def update_banner(
    *, db: Session = Depends(get_db), banner_id: int, banner_in: BannerUpdate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    for key, value in banner_in.model_dump(exclude_unset=True).items():
        setattr(banner, key, value)
    banner.updated_at = datetime.now(UTC)
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return banner

@router.delete("/banners/{banner_id}")
def delete_banner(
    banner_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    banner = db.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    db.delete(banner)
    db.commit()
    return {"message": "Banner deleted successfully"}

# ============================================================================
# Legal Document Endpoints
# ============================================================================

@router.get("/legal/", response_model=List[LegalDocumentRead])
def list_legal_docs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    return db.exec(select(LegalDocument)).all()

@router.post("/legal/", response_model=LegalDocumentRead, status_code=status.HTTP_201_CREATED)
def create_legal_doc(
    *, db: Session = Depends(get_db), doc_in: LegalDocumentCreate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    doc = LegalDocument.model_validate(doc_in)
    doc.published_at = datetime.now(UTC)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.patch("/legal/{doc_id}", response_model=LegalDocumentRead)
def update_legal_doc(
    *, db: Session = Depends(get_db), doc_id: int, doc_in: LegalDocumentUpdate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    doc = db.get(LegalDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in doc_in.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)
    doc.updated_at = datetime.now(UTC)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

@router.delete("/legal/{doc_id}")
def delete_legal_doc(
    doc_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    doc = db.get(LegalDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}

# ============================================================================
# Media Asset Endpoints
# ============================================================================

@router.get("/media/", response_model=List[MediaAssetRead])
def list_media_assets(
    db: Session = Depends(get_db),
    category: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    query = select(MediaAsset)
    if category:
        query = query.where(MediaAsset.category == category)
    return db.exec(query.order_by(MediaAsset.created_at.desc())).all()

@router.post("/media/", response_model=MediaAssetRead, status_code=status.HTTP_201_CREATED)
def create_media_asset(
    *, db: Session = Depends(get_db),
    file_name: str = Query(...), file_type: str = Query(...),
    file_size_bytes: int = Query(...), url: str = Query(...),
    alt_text: Optional[str] = None, category: str = "general",
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    asset = MediaAsset(
        file_name=file_name, file_type=file_type, file_size_bytes=file_size_bytes,
        url=url, alt_text=alt_text, category=category, uploaded_by_id=current_user.id
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

@router.patch("/media/{asset_id}", response_model=MediaAssetRead)
def update_media_asset(
    *, db: Session = Depends(get_db), asset_id: int, asset_in: MediaAssetUpdate,
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    for key, value in asset_in.model_dump(exclude_unset=True).items():
        setattr(asset, key, value)
    asset.updated_at = datetime.now(UTC)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset

@router.delete("/media/{asset_id}")
def delete_media_asset(
    asset_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    db.delete(asset)
    db.commit()
    return {"message": "Asset deleted successfully"}
