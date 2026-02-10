import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.schemas.organization import OrganizationCreate, OrganizationSocialLinkCreate
from app.models.organization import SocialPlatform, OrganizationSocialLink

def test_robust_enum_fix():
    print("Testing robust enum fix...")
    
    # Test case 1: Schema validation with uppercase "INSTAGRAM"
    print("  Scenario 1: Schema Validation")
    data = {"platform": "INSTAGRAM", "url": "https://instagram.com/wezu"}
    obj = OrganizationSocialLinkCreate(**data)
    print(f"    - Input 'INSTAGRAM' -> Schema result: '{obj.platform}' (type: {type(obj.platform)})")
    assert obj.platform == SocialPlatform.INSTAGRAM
    assert obj.platform.value == "instagram"

    # Test case 2: Service layer logic simulation
    print("  Scenario 2: Service Layer Logic")
    # Simulation of what happens in OrganizationService path
    platform_val = obj.platform
    if hasattr(platform_val, 'value'):
        platform_val = platform_val.value
    if isinstance(platform_val, str):
        platform_val = platform_val.lower()
    
    print(f"    - Final value for DB: '{platform_val}'")
    assert platform_val == "instagram"

    # Test case 3: Mixed case via Enum constructor (what SQLModel might do)
    print("  Scenario 3: Enum Case-Insensitivity")
    member = SocialPlatform("InStAgRaM")
    print(f"    - SocialPlatform('InStAgRaM') -> '{member}'")
    assert member == SocialPlatform.INSTAGRAM

if __name__ == "__main__":
    test_robust_enum_fix()
