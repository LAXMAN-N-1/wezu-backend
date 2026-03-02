import httpx
import asyncio

async def test_register():
    url = "http://localhost:8011/api/v1/customer/auth/register"
    payload = {
        "phone_number": "9154345918",
        "full_name": "laxman",
        "password": "password123"
    }
    
    print(f"Testing POST to {url} with payload: {payload}")
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_register())
