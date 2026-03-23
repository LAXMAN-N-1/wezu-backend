
from sqlmodel import Session, select
from app.models.session import UserSession
from app.models.user import User

def test_session_model(session: Session, normal_user: User):
    # Create session
    new_session = UserSession(
        user_id=normal_user.id,
        token_id="test-jti-123",
        ip_address="127.0.0.1",
        user_agent="TestAgent/1.0",
        device_type="web",
        device_id="device-uuid-123",
        device_name="Test Device"
    )
    session.add(new_session)
    session.commit()
    session.refresh(new_session)
    
    assert new_session.id is not None
    assert new_session.device_id == "device-uuid-123"
    assert new_session.device_name == "Test Device"
    
    # Read session
    fetched_session = session.get(UserSession, new_session.id)
    assert fetched_session.user_id == normal_user.id
    
    # Verify relationship
    assert len(normal_user.sessions) > 0
    assert normal_user.sessions[0].id == new_session.id
