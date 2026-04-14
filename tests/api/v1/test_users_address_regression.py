from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api import deps
from app.core.security import get_password_hash
from app.models.address import Address
from app.models.user import User, UserStatus, UserType


def _get_admin_user(session: Session) -> User:
    admin = session.exec(select(User).where(User.email == "admin@test.com")).first()
    assert admin is not None
    return admin


def _create_user_with_addresses(session: Session, email: str) -> User:
    user = User(
        email=email,
        full_name="Address Regression User",
        phone_number=f"888{abs(hash(email)) % 10000000}",
        hashed_password=get_password_hash("Password123!"),
        user_type=UserType.CUSTOMER,
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    session.add(
        Address(
            user_id=user.id,
            address_line1="Default House 42",
            city="Hyderabad",
            state="Telangana",
            postal_code="500001",
            country="India",
            is_default=True,
            type="home",
        )
    )
    session.add(
        Address(
            user_id=user.id,
            address_line1="Office Block B",
            city="Hyderabad",
            state="Telangana",
            postal_code="500081",
            country="India",
            is_default=False,
            type="work",
        )
    )
    session.commit()
    session.refresh(user)
    return user


def test_get_user_profile_uses_addresses_relation(client: TestClient, session: Session):
    admin_user = _get_admin_user(session)
    target_user = _create_user_with_addresses(session, "addr_get@test.com")

    client.app.dependency_overrides[deps.get_current_user] = lambda: admin_user

    response = client.get(f"/api/v1/users/{target_user.id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == target_user.id
    assert payload["address"] is not None
    assert "Hyderabad" in payload["address"]


def test_delete_user_with_addresses_soft_deletes_and_removes_addresses(
    client: TestClient, session: Session
):
    admin_user = _get_admin_user(session)
    target_user = _create_user_with_addresses(session, "addr_delete@test.com")

    client.app.dependency_overrides[deps.get_current_user] = lambda: admin_user

    response = client.delete(f"/api/v1/users/{target_user.id}")
    assert response.status_code == 200

    session.expire_all()
    deleted_user = session.get(User, target_user.id)
    assert deleted_user is not None
    assert deleted_user.is_deleted is True
    assert deleted_user.status == UserStatus.DELETED
    assert deleted_user.email is not None and deleted_user.email.startswith("deleted_")

    remaining_addresses = session.exec(
        select(Address).where(Address.user_id == target_user.id)
    ).all()
    assert remaining_addresses == []
