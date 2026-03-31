import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import text
from app.core.database import engine
from app.core.security import get_password_hash

def restore_admin():
    email = "admin@wezu.com"
    password = "laxman123"
    hashed_password = get_password_hash(password)
    
    with engine.connect() as conn:
        first_user = conn.execute(text("SELECT id FROM users ORDER BY id ASC LIMIT 1")).first()
        if first_user:
            conn.execute(
                text("UPDATE users SET email = :email, hashed_password = :hp, is_superuser = true, status = 'ACTIVE'::userstatus, user_type = 'ADMIN'::usertype WHERE id = :id"),
                {"hp": hashed_password, "email": email, "id": first_user.id}
            )
            conn.commit()
            print(f"Hijacked existing user {first_user.id} to {email}")
        else:
            print("No users exist in the database! Cannot hijack.")

if __name__ == "__main__":
    restore_admin()
