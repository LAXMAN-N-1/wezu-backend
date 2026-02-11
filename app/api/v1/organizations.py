from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlmodel import Session
from typing import List, Optional
from app.api import deps
from app.models.user import User
from app.schemas.organization import OrganizationRead, OrganizationCreate, OrganizationUpdate
from app.services.organization import organization_service

router = APIRouter()

@router.get("/", response_model=List[OrganizationRead])
async def read_organizations(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.check_permission("organizations", "view")),
    db: Session = Depends(deps.get_db),
):
    """List all organizations"""
    return organization_service.get_organizations(db, skip=skip, limit=limit)

@router.get("/{organization_id}", response_model=OrganizationRead)
async def read_organization(
    organization_id: int,
    current_user: User = Depends(deps.check_permission("organizations", "view")),
    db: Session = Depends(deps.get_db),
):
    """Get organization details by ID"""
    organization = organization_service.get_organization_by_id(db, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization

@router.post("/", response_model=OrganizationRead)
async def create_organization(
    org_in: OrganizationCreate,
    current_user: User = Depends(deps.check_permission("organizations", "create")),
    db: Session = Depends(deps.get_db),
):
    """Create a new organization"""
    return organization_service.create_organization(db, org_in)

@router.patch("/{organization_id}", response_model=OrganizationRead)
async def update_organization(
    organization_id: int,
    org_in: OrganizationUpdate,
    current_user: User = Depends(deps.check_permission("organizations", "edit")),
    db: Session = Depends(deps.get_db),
):
    """Update organization details"""
    organization = organization_service.update_organization(db, organization_id, org_in)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization

@router.delete("/{organization_id}", response_model=OrganizationRead)
async def delete_organization(
    organization_id: int,
    current_user: User = Depends(deps.check_permission("organizations", "delete")),
    db: Session = Depends(deps.get_db),
):
    """Delete an organization"""
    organization = organization_service.delete_organization(db, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization

@router.post("/{organization_id}/logo", response_model=OrganizationRead)
async def upload_organization_logo(
    organization_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.check_permission("organizations", "edit")),
    db: Session = Depends(deps.get_db),
):
    """Upload organization logo with pixel validation"""
    organization = await organization_service.upload_logo(db, organization_id, file)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization
