from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.api import deps
from app.models.rbac import Role, Permission
from typing import List, Any

router = APIRouter()

@router.post("/roles")
def create_role(
    role_in: Any, # Simple dict for now, should be schema
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Dynamic Role Creation (Part 1.1)
    """
    new_role = Role(
        name=role_in["name"],
        description=role_in.get("description"),
        category=role_in.get("category", "staff"),
        level=role_in.get("level", 5),
        parent_id=role_in.get("parent_id")
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

@router.get("/permissions")
def list_permissions(
    db: Session = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_superuser),
) -> List[Permission]:
    """
    List all available permissions for role assignment.
    """
    return db.exec(select(Permission)).all()
