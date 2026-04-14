from sqlmodel import create_engine, Session, text, select
from app.core.config import settings
from app.models.user import User
from app.models.battery_catalog import BatteryCatalog

def verify_all():
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as session:
        # Check user
        user = session.exec(select(User).where(User.phone_number == "9154345918")).first()
        if user:
            print(f"Verified User: {user.phone_number}, ID: {user.id}")
        else:
            print("User NOT found!")

        # Check column in battery_catalog
        try:
            res = session.execute(text("SELECT capacity_ah FROM battery_catalog LIMIT 1")).fetchone()
            print("Verified capacity_ah column exists in battery_catalog.")
        except Exception as e:
            print(f"Column capacity_ah check failed: {e}")

        # Check enums
        try:
            res = session.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'transactiontype'")).fetchall()
            labels = [r[0] for r in res]
            print(f"TransactionType enum labels in DB: {labels}")
        except Exception as e:
            print(f"Enum check failed: {e}")

if __name__ == "__main__":
    verify_all()
