from app.core.database import engine
from sqlmodel import Session, text

def check():
    with Session(engine) as session:
        products = session.exec(text("SELECT id, name FROM products")).all()
        print(f"Products: {len(products)}")
        
        stations = session.exec(text("SELECT id, name FROM stations")).all()
        print(f"Stations: {len(stations)}")
        
check()
