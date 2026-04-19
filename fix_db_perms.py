import datetime
if not hasattr(datetime, 'UTC'):
    datetime.UTC = datetime.timezone.utc

import sys
from sqlmodel import Session, select
from app.db.session import engine
from app.models.user import User
from app.models.rbac import Role, RolePermission
from app.core.rbac import PERMISSIONS

with Session(engine) as session:
    user = session.exec(select(User).where(User.email == 'warehouse@wezu.com')).first()
    if user:
        roles = []
        if getattr(user, "role", None):
            roles.append(user.role)
        roles.extend(getattr(user, "roles", []))
        
        needed = {"battery:read", "warehouse:read", "order:read", "driver:read", "logistics:read", "logistics:write", "order:write"}
        
        for role in roles:
            print(f"Role: {role.name}")
            existing_perms = {p.slug for p in getattr(role, "permissions", [])}
            missing = needed - existing_perms
            
            for slug in missing:
                rp = RolePermission(role_id=role.id, slug=slug)
                session.add(rp)
                print(f"Added {slug} to {role.name}")
        
        session.commit()
    else:
        print("User not found")
