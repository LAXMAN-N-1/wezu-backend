"""Fix the dealer@wezu.com password hash in the database."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import ALL models to satisfy SQLAlchemy relationship resolution
from app.models.all import *  # noqa
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

db = SessionLocal()
user = db.query(User).filter(User.email == "dealer@wezu.com").first()
if not user:
    print("ERROR: dealer@wezu.com not found in DB")
    sys.exit(1)

print(f"Current hash (first 40 chars): {str(user.hashed_password)[:40]}")
new_hash = get_password_hash("laxman123")
print(f"New hash    (first 40 chars): {new_hash[:40]}")
user.hashed_password = new_hash
db.commit()
print("✅ dealer@wezu.com password updated to 'laxman123'")
db.close()
