from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.db.session import get_session
from app.models.user import User
from app.models.banner import Banner
from app.schemas.banner import BannerCreate, BannerUpdate, BannerRead
from app.api.deps import get_current_active_admin
from datetime import datetime, UTC

router = APIRouter()

@router.get("/", response_model=List[BannerRead])
def read_banners(
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    query = select(Banner).order_by(Banner.priority.desc())
    banners = session.exec(query).all()
    return banners

@router.post("/", response_model=BannerRead)
def create_banner(
    *,
    session: Session = Depends(get_session),
    banner_in: BannerCreate,
    admin: User = Depends(get_current_active_admin),
):
    db_banner = Banner.model_validate(banner_in)
    session.add(db_banner)
    session.commit()
    session.refresh(db_banner)
    return db_banner

@router.patch("/{banner_id}", response_model=BannerRead)
def update_banner(
    *,
    session: Session = Depends(get_session),
    banner_id: int,
    banner_in: BannerUpdate,
    admin: User = Depends(get_current_active_admin),
):
    db_banner = session.get(Banner, banner_id)
    if not db_banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    banner_data = banner_in.model_dump(exclude_unset=True)
    for key, value in banner_data.items():
        setattr(db_banner, key, value)
    
    db_banner.updated_at = datetime.now(UTC)
    session.add(db_banner)
    session.commit()
    session.refresh(db_banner)
    return db_banner

@router.delete("/{banner_id}")
def delete_banner(
    banner_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    banner = session.get(Banner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    session.delete(banner)
    session.commit()
    return {"ok": True}
