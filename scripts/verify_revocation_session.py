import asyncio
import sys
import os
from httpx import AsyncClient, ASGITransport

# Add parent directory to path to allow importing app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

BASE_PREFIX = "/api/v1"

async def verify_revocation():
    print("1. Registering/Logging in User (Async)...")
    email = "revocation_test_async@example.com"
    password = "password123"
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        
        # Try login first
        login_data = {"username": email, "password": password}
        response = await client.post(f"{BASE_PREFIX}/auth/login", data=login_data)
        
        if response.status_code != 200:
            print("   User not found, registering...")
            reg_data = {
                "email": email,
                "password": password,
                "full_name": "Revocation Verify",
                "phone_number": "5555555555"
            }
            res = await client.post(f"{BASE_PREFIX}/auth/register", json=reg_data)
            if res.status_code != 200:
                print(f"   Registration failed: {res.text}")
                
            # Login again
            response = await client.post(f"{BASE_PREFIX}/auth/login", data=login_data)
            if response.status_code != 200:
                print(f"   Login failed: {response.text}")
                sys.exit(1)

        token_data = response.json()
        access_token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        print("   Login successful. Access Token obtained.")

        print("\n2. Verifying Active Session (Pre-Check)...")
        res = await client.get(f"{BASE_PREFIX}/users/me", headers=headers)
        if res.status_code == 200:
            print("   Success: /users/me is accessible.")
        else:
            print(f"   Failed: /users/me returned {res.status_code}")
            print(f"   Response: {res.text}")
            sys.exit(1)

        print("\n3. Listing Sessions to identify current ID...")
        res = await client.get(f"{BASE_PREFIX}/sessions/list", headers=headers)
        if res.status_code != 200:
            print(f"   Failed to list sessions: {res.text}")
            sys.exit(1)
            
        sessions = res.json()
        current_session_id = None
        
        print(f"   Found {len(sessions)} active sessions.")
        
        for s in sessions:
            if s.get("is_current"):
                current_session_id = s["id"]
                print(f"   Identified current session: {current_session_id} (is_current=True)")
                break
                
        if not current_session_id and sessions:
            current_session_id = sessions[-1]["id"]
            print(f"   Fallback: Using last session ID: {current_session_id}")
            
        if not current_session_id:
            print("   No sessions found!")
            sys.exit(1)

        print(f"\n4. Revoking Session {current_session_id}...")
        res = await client.post(f"{BASE_PREFIX}/sessions/revoke/{current_session_id}", headers=headers)
        if res.status_code == 200:
            print("   Session revoked successfully.")
        else:
            print(f"   Failed to revoke session: {res.status_code} - {res.text}")
            sys.exit(1)

        print("\n5. Verifying Revocation (Post-Check)...")
        # Try accessing protected endpoint again
        res = await client.get(f"{BASE_PREFIX}/users/me", headers=headers)
        
        if res.status_code == 401:
            print("   SUCCESS: /users/me returned 401 Unauthorized as expected.")
        else:
            print(f"   FAILURE: /users/me returned {res.status_code}. Expected 401.")
            print(f"   Response: {res.text}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(verify_revocation())
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
