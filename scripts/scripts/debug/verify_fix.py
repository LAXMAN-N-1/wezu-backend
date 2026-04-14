from sqlmodel import Session, select
from app.db.session import engine
from app.models import User, TwoFactorAuth, VideoKYCSession, Favorite, Alert, RentalEvent, ChargingQueue

try:
    with Session(engine) as session:
        # Triggering a query to force mapper initialization
        session.exec(select(User).limit(1)).all()
        print("Verification SUCCESS: All mappers initialized correctly.")
except Exception as e:
    print(f"Verification FAILED: {e}")
    import traceback
    traceback.print_exc()
