import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.schemas.organization import OrganizationSocialLinkCreate
from app.models.organization import SocialPlatform

def test_enum_fix():
    print("Testing OrganizationSocialLinkCreate with uppercase platform...")
    
    # Test case 1: Uppercase "INSTAGRAM"
    try:
        data = {"platform": "INSTAGRAM", "url": "https://instagram.com/wezu"}
        obj = OrganizationSocialLinkCreate(**data)
        print(f"SUCCESS: 'INSTAGRAM' converted to '{obj.platform}'")
        assert obj.platform == SocialPlatform.INSTAGRAM
    except Exception as e:
        print(f"FAILED: Could not validate 'INSTAGRAM'. Error: {e}")

    # Test case 2: Mixed case "FaceBook"
    try:
        data = {"platform": "FaceBook", "url": "https://facebook.com/wezu"}
        obj = OrganizationSocialLinkCreate(**data)
        print(f"SUCCESS: 'FaceBook' converted to '{obj.platform}'")
        assert obj.platform == SocialPlatform.FACEBOOK
    except Exception as e:
        print(f"FAILED: Could not validate 'FaceBook'. Error: {e}")

    # Test case 3: Invalid platform
    try:
        data = {"platform": "INVALID", "url": "https://example.com"}
        OrganizationSocialLinkCreate(**data)
        print("FAILED: 'INVALID' should have failed validation")
    except Exception:
        print("SUCCESS: 'INVALID' correctly failed validation")

if __name__ == "__main__":
    test_enum_fix()
