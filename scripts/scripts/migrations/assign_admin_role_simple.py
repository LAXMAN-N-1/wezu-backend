from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.models.rbac import Role, UserRole
import app.models

def assign():
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        role = session.exec(select(Role).where(Role.name == "super_admin")).first()
        
        if user and role:
            # Check if association already exists
            existing = session.exec(select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id
            )).first()
            
            if not existing:
                assoc = UserRole(user_id=user.id, role_id=role.id)
                session.add(assoc)
                session.commit()
                print(f"Assigned super_admin (ID {role.id}) to {user.email} (ID {user.id})")
            else:
                print("Role already assigned.")
        else:
            print(f"User found: {bool(user)}, Role found: {bool(role)}")

if __name__ == "__main__":
    assign()
