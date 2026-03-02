import asyncio
from httpx import AsyncClient
from app.main import app

async def test_fail_password():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        print("\n--- Testing Login with unknown number ---")
        response = await ac.post(
            "/api/v1/customer/auth/login", 
            data={
                "username": "7007297384",
                "password": "wrongpassword"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_fail_password())
