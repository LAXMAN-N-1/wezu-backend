import os
import sys
from sqlmodel import Session, select

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(parent_dir)

from app.db.session import engine
from app.models.battery import Battery
from app.models.dealer import DealerProfile
from app.models.user import User

with Session(engine) as db:
    print("=== LAX BATTERIES ===")
    batteries = db.exec(select(Battery).where(Battery.serial_number.like("%LAX%"))).all()
    print(f"Found {len(batteries)} batteries with LAX in serial number")
    if batteries:
        print(f"Sample: {batteries[0].serial_number}")

    print("=== LAX OR WEZU DEALERS ===")
    dealers = db.exec(select(DealerProfile).where(DealerProfile.business_name.like("%laxman%"))).all()
    print(f"Found {len(dealers)} dealers with 'laxman' in name")
    if dealers:
        print(f"Sample: {dealers[0].business_name}")
    
    users = db.exec(select(User).where(User.full_name.like("%laxman%"))).all()
    print(f"Found {len(users)} users with 'laxman' in full name")
    if users:
        print(f"Sample: {users[0].full_name}")
