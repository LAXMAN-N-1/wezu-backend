import asyncio
from httpx import AsyncClient
from app.main import app

async def test_login():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        print("\n--- Testing Login ---")
        
        # Testing the one with +91 space that frontend might send
        response1 = await ac.post(
            "/api/v1/customer/auth/login", 
            data={
                "username": "+91 7997297384",
                "password": "123456789"
            }
        )
        print(f"Status 1: {response1.status_code}")
        print(f"Response 1: {response1.text}")

        # Testing the exact number from earlier requests
        response2 = await ac.post(
            "/api/v1/customer/auth/login", 
            data={
                "username": "7007297384",
                "password": "123456789"
            }
        )
        print(f"Status 2: {response2.status_code}")
        print(f"Response 2: {response2.text}")

if __name__ == "__main__":
    asyncio.run(test_login())
