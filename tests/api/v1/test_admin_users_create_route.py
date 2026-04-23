from sqlmodel import Session, select

from app.api import deps
from app.models.user import User, UserStatus, UserType


def _set_admin_override(client, session: Session) -> User:
    admin_user = session.exec(select(User).where(User.email == "admin@test.com")).first()
    assert admin_user is not None
    admin_user.status = UserStatus.ACTIVE
    admin_user.user_type = UserType.ADMIN
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)
    client.app.dependency_overrides[deps.get_current_active_admin] = lambda: admin_user
    return admin_user


def test_admin_create_user_accepts_no_trailing_slash(client, session: Session):
    _set_admin_override(client, session)

    response = client.post(
        "/api/v1/admin/users",
        json={
            "full_name": "No Slash User",
            "email": "no-slash-user@test.com",
            "password": "Welcome@123",
            "role_name": "admin",
            "status": "active",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == "no-slash-user@test.com"

    created = session.exec(
        select(User).where(User.email == "no-slash-user@test.com")
    ).first()
    assert created is not None
