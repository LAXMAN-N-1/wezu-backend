from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.api import deps
from app.core.database import get_db
from app.schemas.role_right import RoleRightCreate, RoleRightRead, RoleRightUpdate
from app.services.role_right_service import role_right_service

router = APIRouter()

@router.post("/", response_model=RoleRightRead, status_code=status.HTTP_201_CREATED)
def create_role_right(
    *,
    db: Session = Depends(get_db),
    right_in: RoleRightCreate,
    current_user = Depends(deps.check_permission("role_rights", "create"))
):
    return role_right_service.create_or_update_role_right(db, right_in)

@router.get("/role/{role_id}", response_model=List[RoleRightRead])
def read_role_rights(
    role_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    return role_right_service.get_role_rights(db, role_id)

@router.put("/{right_id}", response_model=RoleRightRead)
def update_role_right(
    *,
    db: Session = Depends(get_db),
    right_id: int,
    right_in: RoleRightUpdate,
    current_user = Depends(deps.check_permission("role_rights", "edit"))
):
    right = role_right_service.update_role_right(db, right_id, right_in)
    if not right:
        raise HTTPException(status_code=404, detail="RoleRight not found")
    return right
