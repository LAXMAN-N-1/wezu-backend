from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.api import deps
from app.models.user import User
from app.models.favorite import Favorite
from app.models.station import Station
from app.schemas.station import StationResponse

router = APIRouter()

@router.post("/{station_id}", response_model=dict)
async def add_favorite(
    station_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    existing = db.exec(select(Favorite).where(Favorite.user_id == current_user.id, Favorite.station_id == station_id)).first()
    if existing:
        return {"status": "already_favorited"}
        
    fav = Favorite(user_id=current_user.id, station_id=station_id)
    db.add(fav)
    db.commit()
    return {"status": "added"}

@router.delete("/{station_id}", response_model=dict)
async def remove_favorite(
    station_id: int,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    fav = db.exec(select(Favorite).where(Favorite.user_id == current_user.id, Favorite.station_id == station_id)).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
        
    db.delete(fav)
    db.commit()
    return {"status": "removed"}

@router.get("/", response_model=List[StationResponse])
async def get_favorites(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
):
    # Join Favorite and Station
    query = select(Station).join(Favorite).where(Favorite.user_id == current_user.id)
    return db.exec(query).all()
