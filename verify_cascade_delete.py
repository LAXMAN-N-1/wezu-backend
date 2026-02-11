import sys
import os
from sqlmodel import Session, select

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.core.database import engine
from app.models.organization import Organization, OrganizationSocialLink
from app.schemas.organization import OrganizationCreate, OrganizationSocialLinkCreate
from app.services.organization import organization_service

def test_cascade_delete():
    print("Testing Organization cascade delete...")
    
    with Session(engine) as db:
        # 1. Create a dummy organization with social links
        org_in = OrganizationCreate(
            name="Cascade Test Org",
            code="TEST-CASCADE-001",
            social_links=[
                OrganizationSocialLinkCreate(platform="instagram", url="https://inst.com/test")
            ]
        )
        db_org = organization_service.create_organization(db, org_in)
        org_id = db_org.id
        print(f"  Created Org ID: {org_id}")
        
        # Verify link exists
        link = db.exec(select(OrganizationSocialLink).where(OrganizationSocialLink.organization_id == org_id)).first()
        if not link:
            print("  FAILED: Link was not created")
            return
        link_id = link.id
        print(f"  Created Social Link ID: {link_id}")
        
        # 2. Delete the organization
        print(f"  Deleting Org {org_id}...")
        organization_service.delete_organization(db, org_id)
        
        # 3. Verify organization is gone
        deleted_org = db.get(Organization, org_id)
        if deleted_org:
            print("  FAILED: Organization still exists")
            return
        print("  SUCCESS: Organization deleted")
        
        # 4. Verify link is gone (Cascade check)
        deleted_link = db.get(OrganizationSocialLink, link_id)
        if deleted_link:
            print(f"  FAILED: Social Link {link_id} still exists (No Cascade)")
        else:
            print("  SUCCESS: Social Link deleted via cascade")

if __name__ == "__main__":
    test_cascade_delete()
