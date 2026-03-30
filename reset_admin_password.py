
from sqlmodel import Session, create_engine, select
from app.models.user import User
from app.core.config import settings
from app.core.security import get_password_hash

def reset_password(email: str, new_password: str):
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as session:
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        if user:
            user.hashed_password = get_password_hash(new_password)
            session.add(user)
            session.commit()
            print(f"Password reset successful for {email}")
        else:
            print(f"User with email {email} not found")

if __name__ == "__main__":
    reset_password("laxmanlaxman1629@gmail.com", "laxman123")
