from sqlmodel import Session, create_engine, text
from app.core.config import settings

def update_test_reports():
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as session:
        # Update existing records where created_by is the user's name
        result = session.execute(
            text("UPDATE test_reports SET created_by = 'dev' WHERE created_by = 'kamboja Srilaxmi'")
        )
        session.commit()
        print(f"Updated {result.rowcount} records to 'dev'.")

if __name__ == "__main__":
    update_test_reports()
