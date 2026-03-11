from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.models.rbac import Role
import app.models # Ensure all mappers are initialized

def assign_admin_role():
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not user:
            print("Admin user not found.")
            return

        # Check for both role name variations
        role_names = ["Super Admin", "super_admin"]
        roles = session.exec(select(Role).where(Role.name.in_(role_names))).all()
        
        if not roles:
            print("Super Admin roles not found.")
            return

        for role in roles:
            if role not in user.roles:
                user.roles.append(role)
                print(f"Assigned role: {role.name}")
        
        session.add(user)
        session.commit()
        print("Role assignment complete.")

if __name__ == "__main__":
    assign_admin_role()
