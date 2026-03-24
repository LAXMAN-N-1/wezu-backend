
import os
from sqlmodel import Session, create_engine, select
from app.models.user import User
from app.core.config import settings

def check_users():
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as session:
        statement = select(User)
        results = session.exec(statement).all()
        print(f"Total users: {len(results)}")
        for user in results:
            print(f"ID: {user.id}, Email: {user.email}, Status: {user.status}, Role ID: {user.role_id}")
            # roles are usually many-to-many or many-to-one, let's see if we can get role name
            if hasattr(user, 'role') and user.role:
                print(f"  Role: {user.role.name}")
            elif hasattr(user, 'roles') and user.roles:
                print(f"  Roles: {[r.name for r in user.roles]}")

if __name__ == "__main__":
    check_users()
