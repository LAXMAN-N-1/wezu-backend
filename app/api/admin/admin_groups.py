from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List
from datetime import datetime, UTC

from app.api import deps
from app.core.config import settings
from app.models.admin_group import AdminGroup
from app.models.admin_user import AdminUser
from app.schemas.admin_group import (
    AdminGroupCreate,
    AdminGroupUpdate,
    AdminGroupResponse,
    AdminGroupWithCount
)
from app.utils.runtime_cache import cached_call, invalidate_cache

router = APIRouter()


def _invalidate_admin_group_cache() -> None:
    invalidate_cache("admin-groups")

@router.get("/", response_model=List[AdminGroupWithCount])
def read_admin_groups(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
):
    """
    Retrieve all admin groups, along with their active member counts.
    """
    def _load_groups() -> list[dict]:
        rows = db.exec(
            select(
                AdminGroup.id,
                AdminGroup.name,
                AdminGroup.description,
                AdminGroup.is_active,
                AdminGroup.created_at,
                AdminGroup.updated_at,
                func.coalesce(func.count(AdminUser.id), 0),
            )
            .select_from(AdminGroup)
            .join(AdminUser, AdminUser.admin_group_id == AdminGroup.id, isouter=True)
            .group_by(
                AdminGroup.id,
                AdminGroup.name,
                AdminGroup.description,
                AdminGroup.is_active,
                AdminGroup.created_at,
                AdminGroup.updated_at,
            )
            .order_by(AdminGroup.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).all()

        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "is_active": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "member_count": row[6],
            }
            for row in rows
        ]

    rows = cached_call(
        "admin-groups",
        skip,
        limit,
        ttl_seconds=settings.USER_ADMIN_CACHE_TTL_SECONDS,
        call=_load_groups,
    )
    return [AdminGroupWithCount.model_validate(row) for row in rows]

@router.post("/", response_model=AdminGroupResponse, status_code=status.HTTP_201_CREATED)
def create_admin_group(
    *,
    db: Session = Depends(deps.get_db),
    group_in: AdminGroupCreate,
):
    """
    Create new admin group.
    """
    # Check for duplicate
    existing = db.exec(select(AdminGroup).where(AdminGroup.name == group_in.name)).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="The admin group with this name already exists in the system.",
        )
    
    db_group = AdminGroup.from_orm(group_in)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    _invalidate_admin_group_cache()
    return db_group

@router.put("/{group_id}", response_model=AdminGroupResponse)
def update_admin_group(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int,
    group_in: AdminGroupUpdate,
):
    """
    Update an admin group.
    """
    group = db.get(AdminGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Admin group not found")
        
    if group_in.name and group_in.name != group.name:
        existing = db.exec(select(AdminGroup).where(AdminGroup.name == group_in.name)).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Another admin group with this name already exists.",
            )

    update_data = group_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)
        
    group.updated_at = datetime.now(UTC)
    db.add(group)
    db.commit()
    db.refresh(group)
    _invalidate_admin_group_cache()
    return group

@router.delete("/{group_id}", response_model=dict)
def delete_admin_group(
    *,
    db: Session = Depends(deps.get_db),
    group_id: int,
):
    """
    Delete an admin group.
    """
    group = db.get(AdminGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Admin group not found")
        
    # Check if there are members
    count_statement = select(func.count(AdminUser.id)).where(AdminUser.admin_group_id == group_id)
    member_count = db.exec(count_statement).first() or 0
    
    if member_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete group because {member_count} users are assigned to it.",
        )
        
    db.delete(group)
    db.commit()
    _invalidate_admin_group_cache()
    return {"ok": True}
