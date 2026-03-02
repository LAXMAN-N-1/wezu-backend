from app.db.session import engine
from sqlmodel import Session, select
from app.models.user import User

def test():
    with Session(engine) as session:
        user = session.exec(select(User).where(User.phone_number == "7997297384")).first()
        if user:
            print(f"ID: {user.id}")
            print(f"Phone: {user.phone_number}")
            print(f"Name: {user.full_name}")
            print(f"Status: {user.status}")
            print(f"Role: {user.role.name if user.role else 'None'}")
        else:
            print("User not found!")

if __name__ == "__main__":
    test()
