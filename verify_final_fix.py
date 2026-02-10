import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.models.organization import SocialPlatform
from app.schemas.organization import OrganizationSocialLinkCreate

def test_final_enum_fix():
    print("Testing final enum fix (lowercase members)...")
    
    # Check enum members
    print(f"  SocialPlatform.instagram.name: '{SocialPlatform.instagram.name}'")
    assert SocialPlatform.instagram.name == "instagram"
    
    # Check casing robustness via constructor
    inst = SocialPlatform("INSTAGRAM")
    print(f"  SocialPlatform('INSTAGRAM'): {inst}")
    assert inst == SocialPlatform.instagram
    assert inst.name == "instagram"
    
    # Check schema validation
    data = {"platform": "INSTAGRAM", "url": "https://instagram.com/wezu"}
    obj = OrganizationSocialLinkCreate(**data)
    print(f"  Schema result for 'INSTAGRAM': {obj.platform} (name: {obj.platform.name})")
    assert obj.platform == SocialPlatform.instagram
    assert obj.platform.name == "instagram"

if __name__ == "__main__":
    test_final_enum_fix()
