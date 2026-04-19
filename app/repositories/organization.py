from __future__ import annotations
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.repositories.base_repository import BaseRepository

class OrganizationRepository(BaseRepository[Organization, OrganizationCreate, OrganizationUpdate]):
    """Organization-specific data access methods"""
    
    def __init__(self):
        super().__init__(Organization)

# Singleton instance
organization_repository = OrganizationRepository()
