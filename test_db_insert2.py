from app.db.session import engine
from sqlmodel import Session, text

def test():
    with Session(engine) as session:
        result = session.exec(text("SELECT column_name, is_nullable, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'users';"))
        for row in result:
            print(row)

if __name__ == "__main__":
    test()
