from sqlmodel import Session, select
from app.core.database import engine
from app.models.rbac import Role

def list_roles():
    with Session(engine) as session:
        roles = session.exec(select(Role)).all()
        for role in roles:
            print(f"ID: {role.id}, Name: {role.name}")

if __name__ == "__main__":
    list_roles()
