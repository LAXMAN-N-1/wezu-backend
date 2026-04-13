from sqlmodel import Session, select
from app.db.session import engine
from app.models import User

def check_user():
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if user:
            print(f"✅ User found: {user.email}")
            print(f"Role ID: {user.role_id}")
            print(f"User Type: {user.user_type}")
        else:
            print("❌ User NOT found: admin@wezu.com")

if __name__ == "__main__":
    check_user()
