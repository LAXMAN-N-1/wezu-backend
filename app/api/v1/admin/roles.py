from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from typing import List
from app.api import deps
from app.services.rbac_service import rbac_service
from app.schemas.rbac import RoleCreate, RoleUpdate, RoleResponse, PermissionResponse
from app.models.rbac import Role
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[RoleResponse])
async def list_roles(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """List all available roles and their permissions"""
    return rbac_service.list_roles(db)

@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """List all available permissions in the system"""
    return rbac_service.list_permissions(db)

@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_in: RoleCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Create a new custom role with permissions"""
    if rbac_service.get_role_by_name(db, role_in.name):
        raise HTTPException(status_code=400, detail="Role already exists")
    
    role = Role(
        name=role_in.name,
        description=role_in.description,
        category=role_in.category,
        level=role_in.level,
        is_system_role=False
    )
    return rbac_service.create_role(db, role, role_in.permission_ids)

@router.put("/{id}", response_model=RoleResponse)
async def update_role(
    id: int,
    role_in: RoleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser),
):
    """Update a role's metadata and permissions"""
    update_data = role_in.model_dump(exclude={"permission_ids"}, exclude_unset=True)
    role = rbac_service.update_role(db, id, update_data, role_in.permission_ids)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role
