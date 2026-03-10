import asyncio
from httpx import AsyncClient
from app.main import app

async def test_verify():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        print("\n--- Testing OTP Verification ---")
        response = await ac.post(
            "/api/v1/customer/auth/register/verify-otp", 
            json={
                "target": "7007297384",
                "code": "964056",
                "purpose": "registration",
                "full_name": "bindu"
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_verify())
