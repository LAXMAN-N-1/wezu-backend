from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
from typing import List, Optional
from app.db.session import get_session
from app.models.user import User
from app.models.media import MediaAsset
from app.schemas.media import MediaAssetRead, MediaAssetUpdate
from app.api.deps import get_current_active_admin
from datetime import datetime
import os

router = APIRouter()

# In a real app, this would use a Storage Service (S3/Local)
# For this task, we assume the upload logic is handled and we record the metadata

@router.get("/", response_model=List[MediaAssetRead])
def list_media_assets(
    session: Session = Depends(get_session),
    category: Optional[str] = None,
    admin: User = Depends(get_current_active_admin),
):
    query = select(MediaAsset)
    if category:
        query = query.where(MediaAsset.category == category)
    return session.exec(query.order_by(MediaAsset.created_at.desc())).all()

@router.post("/upload", response_model=MediaAssetRead)
async def upload_media(
    file: UploadFile = File(...),
    category: str = Form("general"),
    alt_text: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    # Mocking storage upload - would return a real URL
    file_url = f"https://storage.wezu.com/uploads/{file.filename}"
    
    db_asset = MediaAsset(
        file_name=file.filename,
        file_type=file.content_type,
        file_size_bytes=0, # In reality, get from file.file.tell() etc
        url=file_url,
        alt_text=alt_text,
        category=category,
        uploaded_by_id=admin.id
    )
    
    session.add(db_asset)
    session.commit()
    session.refresh(db_asset)
    return db_asset

@router.delete("/{asset_id}")
def delete_media_asset(
    asset_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(get_current_active_admin),
):
    asset = session.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    session.delete(asset)
    session.commit()
    return {"ok": True}
