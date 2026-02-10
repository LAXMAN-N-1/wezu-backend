from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.schemas.branch import BranchRead, BranchCreate, BranchUpdate
from app.services.branch import branch_service

router = APIRouter()

@router.get("/", response_model=List[BranchRead])
async def read_branches(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
):
    """List all branches"""
    return branch_service.get_branches(db, skip=skip, limit=limit)

@router.get("/{branch_id}", response_model=BranchRead)
async def read_branch(
    branch_id: int,
    db: Session = Depends(deps.get_db),
):
    """Get branch details by ID"""
    branch = branch_service.get_branch_by_id(db, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch

@router.post("/", response_model=BranchRead)
async def create_branch(
    branch_in: BranchCreate,
    current_user: User = Depends(deps.check_permission("branches", "create")),
    db: Session = Depends(deps.get_db),
):
    """Create a new branch (Superadmin only)"""
    return branch_service.create_branch(db, branch_in)

@router.patch("/{branch_id}", response_model=BranchRead)
async def update_branch(
    branch_id: int,
    branch_in: BranchUpdate,
    current_user: User = Depends(deps.check_permission("branches", "edit")),
    db: Session = Depends(deps.get_db),
):
    """Update branch details (Superadmin only)"""
    branch = branch_service.update_branch(db, branch_id, branch_in)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch

@router.delete("/{branch_id}", response_model=BranchRead)
async def delete_branch(
    branch_id: int,
    current_user: User = Depends(deps.check_permission("branches", "delete")),
    db: Session = Depends(deps.get_db),
):
    """Delete a branch (Superadmin only)"""
    branch = branch_service.delete_branch(db, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch
