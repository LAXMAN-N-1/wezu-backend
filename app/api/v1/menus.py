from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.api import deps
from app.core.database import get_db
from app.schemas.menu import MenuCreate, MenuRead, MenuUpdate, MenuReadWithChildren
from app.services.menu_service import menu_service

router = APIRouter()

@router.post("/", response_model=MenuRead, status_code=status.HTTP_201_CREATED)
def create_menu(
    *,
    db: Session = Depends(get_db),
    menu_in: MenuCreate,
    current_user = Depends(deps.check_permission("menus", "create"))
):
    return menu_service.create_menu(db, menu_in)

@router.get("/", response_model=List[MenuRead])
def read_menus(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(deps.get_current_user)
):
    return menu_service.get_menus(db, skip=skip, limit=limit)

@router.get("/{menu_id}", response_model=MenuRead)
def read_menu(
    menu_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    menu = menu_service.get_menu(db, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")
    return menu

@router.put("/{menu_id}", response_model=MenuRead)
def update_menu(
    *,
    db: Session = Depends(get_db),
    menu_id: int,
    menu_in: MenuUpdate,
    current_user = Depends(deps.check_permission("menus", "edit"))
):
    menu = menu_service.update_menu(db, menu_id, menu_in)
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")
    return menu

@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu(
    *,
    db: Session = Depends(get_db),
    menu_id: int,
    current_user = Depends(deps.check_permission("menus", "delete"))
):
    if not menu_service.delete_menu(db, menu_id):
        raise HTTPException(status_code=404, detail="Menu not found")
    return None
