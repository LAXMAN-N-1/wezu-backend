import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select, func
from app.core.database import engine
from app.models.rental import Rental
from app.models.user import User
from app.models.battery import Battery

def check_db():

    with Session(engine) as db:
        users = db.exec(select(func.count(User.id))).one()
        rentals = db.exec(select(func.count(Rental.id))).one()
        batteries = db.exec(select(func.count(Battery.id))).one()
        rev = db.exec(select(func.sum(Rental.total_price))).one()
        print(f"Users in DB: {users}")
        print(f"Rentals in DB: {rentals}")
        print(f"Batteries in DB: {batteries}")
        print(f"Total Revenue in DB: {rev}")

if __name__ == "__main__":
    check_db()
