import os
from datetime import datetime, UTC

from sqlalchemy import create_engine
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.rbac import Role, UserRole
from app.models.user import User, UserStatus, UserType


EMAIL = "laxmanlaxman1629@gmail.com"
PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)

    with Session(engine) as session:
        role = session.exec(select(Role).where(Role.name == "super_admin")).first()
        if not role:
            role = Role(
                name="super_admin",
                description="Super Administrator with full access",
                category="system",
                level=100,
                is_system_role=True,
                is_active=True,
            )
            session.add(role)
            session.commit()
            session.refresh(role)
            print(f"CREATED_ROLE {role.id} {role.name}")
        else:
            print(f"FOUND_ROLE {role.id} {role.name}")

        user = session.exec(select(User).where(User.email == EMAIL)).first()
        if not user:
            user = User(
                email=EMAIL,
                full_name="Laxman",
                user_type=UserType.ADMIN,
                status=UserStatus.ACTIVE,
                is_superuser=True,
                role_id=role.id,
                hashed_password=get_password_hash(PASSWORD),
                password_changed_at=datetime.now(UTC),
                force_password_change=False,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"CREATED_USER {user.id}")
        else:
            user.user_type = UserType.ADMIN
            user.status = UserStatus.ACTIVE
            user.is_superuser = True
            user.role_id = role.id
            user.hashed_password = get_password_hash(PASSWORD)
            user.password_changed_at = datetime.now(UTC)
            user.force_password_change = False
            user.updated_at = datetime.now(UTC)
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"UPDATED_USER {user.id}")

        links = session.exec(select(UserRole).where(UserRole.user_id == user.id)).all()
        for link in links:
            if link.role_id != role.id:
                session.delete(link)
        session.commit()

        current_link = session.exec(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
            )
        ).first()
        if not current_link:
            session.add(
                UserRole(
                    user_id=user.id,
                    role_id=role.id,
                    notes="Promoted via Codex",
                )
            )
            session.commit()
            print("CREATED_USER_ROLE_LINK")
        else:
            print("FOUND_USER_ROLE_LINK")

        session.refresh(user)
        final_links = session.exec(select(UserRole).where(UserRole.user_id == user.id)).all()
        print(
            "FINAL_USER",
            user.id,
            user.email,
            user.user_type,
            user.status,
            user.is_superuser,
            user.role_id,
        )
        print("FINAL_LINKS", [(link.user_id, link.role_id) for link in final_links])


if __name__ == "__main__":
    main()
