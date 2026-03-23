from sqlmodel import Session, select
from app.db.session import engine
from app.models.user import User
from app.api.deps import get_current_user
from fastapi import Request
import logging
from unittest.mock import MagicMock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_deps")

def debug_auth(token):
    with Session(engine) as db:
        logger.info(f"Testing token: {token[:10]}...")
        try:
            # Replicate the dependency call
            user = get_current_user(db=db, token=token)
            logger.info(f"✅ User found: {user.email}")
            logger.info(f"ID: {user.id}, Superuser: {user.is_superuser}")
        except Exception as e:
            logger.exception("❌ Error in get_current_user")

if __name__ == "__main__":
    # Use the token from token.json
    import json
    with open("token.json", "r") as f:
        data = json.load(f)
        token = data["access_token"]
    debug_auth(token)
