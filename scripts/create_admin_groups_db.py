import sys
import os
import sqlalchemy as sa
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel, text
from app.core.database import engine
from app.models.admin_group import AdminGroup
from app.models.admin_user import AdminUser

def run():
    print("Creating admin_groups table...")
    AdminGroup.__table__.create(engine, checkfirst=True)
    print("Table admin_groups created successfully.")

    print("Adding admin_group_id column to admin_users table (if not exists)...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS admin_group_id INTEGER REFERENCES admin_groups(id);"))
            conn.commit()
            print("Successfully added admin_group_id foreign key to admin_users.")
        except Exception as e:
            print(f"Error adding column: {e}")

if __name__ == "__main__":
    run()
