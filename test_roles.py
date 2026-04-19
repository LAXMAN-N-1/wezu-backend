import asyncio
from sqlmodel import Session, select
from app.db.session import engine
from app.models.user import User

with Session(engine) as session:
    user = session.exec(select(User).where(User.email == 'warehouse@wezu.com')).first()
    if user:
        print(f"User Type: {user.user_type}")
        print(f"Primary Role NAME: {user.role.name if getattr(user, 'role', None) else None}")
        print(f"Roles: {[r.name for r in getattr(user, 'roles', [])]}")
        
        from app.api.deps import get_user_role_names, INTERNAL_OPERATOR_ROLE_NAMES, LOGISTICS_ROLE_NAMES
        role_names = get_user_role_names(user)
        print(f"Canonical Role Names from deps: {role_names}")
        print(f"Is internal operator? {bool(role_names & INTERNAL_OPERATOR_ROLE_NAMES)}")
        print(f"Is driver? {bool(role_names & {'driver', 'rider', 'courier'})}")
    else:
        print("User not found")
