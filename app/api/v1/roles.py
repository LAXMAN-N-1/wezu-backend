from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.api import deps
from app.core.database import get_db
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.services.role_service import role_service

router = APIRouter()

@router.post("/", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    *,
    db: Session = Depends(get_db),
    role_in: RoleCreate,
    current_user = Depends(deps.check_permission("roles", "create"))
):
    return role_service.create_role(db, role_in)

@router.get("/", response_model=List[RoleRead])
def read_roles(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(deps.get_current_user)
):
    return role_service.get_roles(db, skip=skip, limit=limit)

@router.get("/{role_id}", response_model=RoleRead)
def read_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(deps.get_current_user)
):
    role = role_service.get_role(db, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.put("/{role_id}", response_model=RoleRead)
def update_role(
    *,
    db: Session = Depends(get_db),
    role_id: int,
    role_in: RoleUpdate,
    current_user = Depends(deps.check_permission("roles", "edit"))
):
    role = role_service.update_role(db, role_id, role_in)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    *,
    db: Session = Depends(get_db),
    role_id: int,
    current_user = Depends(deps.check_permission("roles", "delete"))
):
    if not role_service.delete_role(db, role_id):
        raise HTTPException(status_code=404, detail="Role not found")
    return None
