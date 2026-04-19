import app.models.all
from sqlmodel import Session, select
from app.db.session import engine
from app.models.user import User
from app.api.v1.auth import _process_login
from fastapi import Request
import asyncio

async def test():
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == "admin@wezu.com")).first()
        if not user:
            print("User not found!")
            return
        
        print("Forcing password verification to pass by hacking the hashed_password locally...")
        from app.core.security import get_password_hash
        user.hashed_password = get_password_hash("test1234")
        
        from pydantic import BaseModel
        class MockRequest:
            headers = {"user-agent": "test script"}
            client = type("MockClient", (), {"host": "127.0.0.1"})()
            client.host = "127.0.0.1"
            
        print("Calling _process_login()...")
        try:
            result = await _process_login("admin@wezu.com", "test1234", db, MockRequest())
            print("SUCCESS! Token created:", result.access_token[:20])
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("CRASHED:", repr(e))

asyncio.run(test())
