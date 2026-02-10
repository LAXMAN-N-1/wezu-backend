from sqlmodel import Session, select
from app.models.organization import Organization, OrganizationSocialLink
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.repositories.organization import organization_repository
from app.services.storage_service import storage_service
from typing import List, Optional
from fastapi import UploadFile
import io

# Try to import Pillow for pixel validation
try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

class OrganizationService:
    @staticmethod
    def get_organizations(db: Session, skip: int = 0, limit: int = 100) -> List[Organization]:
        return organization_repository.get_multi(db, skip=skip, limit=limit)

    @staticmethod
    def get_organization_by_id(db: Session, organization_id: int) -> Optional[Organization]:
        return organization_repository.get(db, organization_id)

    @staticmethod
    def create_organization(db: Session, org_in: OrganizationCreate) -> Organization:
        # Extract social links from the input
        social_links_data = org_in.social_links or []
        
        db_org = Organization(
            name=org_in.name,
            code=org_in.code,
            website=org_in.website,
            is_active=org_in.is_active
        )
        db.add(db_org)
        db.flush() # Get the ID
        
        # Add social links
        for link_data in social_links_data:
            db_link = OrganizationSocialLink(
                organization_id=db_org.id,
                platform=link_data.platform,
                url=link_data.url
            )
            db.add(db_link)
        
        db.commit()
        db.refresh(db_org)
        return db_org

    @staticmethod
    def update_organization(db: Session, org_id: int, org_in: OrganizationUpdate) -> Optional[Organization]:
        db_org = organization_repository.get(db, org_id)
        if not db_org:
            return None
        
        return organization_repository.update(db, db_obj=db_org, obj_in=org_in)

    @staticmethod
    async def upload_logo(db: Session, org_id: int, file: UploadFile) -> Optional[Organization]:
        db_org = organization_repository.get(db, org_id)
        if not db_org:
            return None
        
        # Read file for validation
        contents = await file.read()
        width, height = None, None
        
        if HAS_PILLOW:
            try:
                img = Image.open(io.BytesIO(contents))
                width, height = img.size
            except Exception:
                pass # Not an image or other error
        
        # Reset file pointer for storage service
        file.file.seek(0)
        
        logo_url = await storage_service.upload_file(file, directory="logos")
        
        db_org.logo_url = logo_url
        db_org.logo_width = width
        db_org.logo_height = height
        
        db.add(db_org)
        db.commit()
        db.refresh(db_org)
        return db_org

    @staticmethod
    def delete_organization(db: Session, org_id: int) -> Optional[Organization]:
        if not organization_repository.exists(db, org_id):
            return None
        return organization_repository.delete(db, id=org_id)

organization_service = OrganizationService()
