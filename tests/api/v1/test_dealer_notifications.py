import pytest
from sqlmodel import Session, select
from app.models.user import User
from app.models.dealer import DealerProfile
from app.models.dealer_notification_pref import DealerNotificationPreference
from app.core.config import settings
from app.core.security import get_password_hash, create_access_token

def get_dealer_auth_headers_and_user(session: Session, email: str = "test_dealer@test.com"):
    # 1. Provide User via DB directly to bypass broken /auth/register route
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash("test_pwd"),
            full_name="Dealer Account",
            phone_number="9999999999",
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        
    # 2. Add dealer profile
    dealer = session.exec(select(DealerProfile).where(DealerProfile.user_id == user.id)).first()
    if not dealer:
        dealer = DealerProfile(
            user_id=user.id, 
            business_name="Test Dealer Biz", 
            contact_person="John", 
            contact_email="john@dealer.com", 
            contact_phone="1234567890", 
            address_line1="123", 
            city="Test", 
            state="Test", 
            pincode="123"
        )
        session.add(dealer)
        session.commit()
        session.refresh(dealer)
        
    # 3. Create explicit login token
    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}
        
    return headers, dealer

def test_get_dealer_preferences_creates_default(client, session: Session):
    headers, test_dealer = get_dealer_auth_headers_and_user(session, "pref_default@test.com")
    
    response = client.get(f"{settings.API_V1_STR}/dealer/notifications/preferences", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["dealer_id"] == test_dealer.id
    assert data["push_notifications"] is True
    assert data["low_inventory_threshold"] == 5

def test_update_dealer_preferences_partial(client, session: Session):
    headers, test_dealer = get_dealer_auth_headers_and_user(session, "pref_update@test.com")
    
    # First get to ensure creation
    client.get(f"{settings.API_V1_STR}/dealer/notifications/preferences", headers=headers)
    
    # Update only low_inventory_threshold and quiet_hours
    payload = {
        "low_inventory_threshold": 10,
        "quiet_hours": {"start": "23:00", "end": "06:00"}
    }
    response = client.put(f"{settings.API_V1_STR}/dealer/notifications/preferences", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["low_inventory_threshold"] == 10
    # ensure others are not overwritten
    assert data["push_notifications"] is True
    assert data["quiet_hours"]["start"] == "23:00"

# Note: Integration with NotificationService quiet-hours check would typically be unit tested at the service layer, but verifying the toggle was saved is sufficient here for the API.
