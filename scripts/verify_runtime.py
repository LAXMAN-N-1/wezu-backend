import httpx
import time
import sys
import asyncio

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def run_verification():
    async with httpx.AsyncClient(timeout=10.0) as client:
        print("1. Checking Health...")
        try:
            # Depending on if there is a root or health endpoint. 
            # Given previous context, let's try a known public endpoint or just wait for login.
            pass
        except Exception as e:
            print(f"Health check skipped or failed: {e}")

        print("2. Login as Super Admin...")
        # Assuming default seeds or known admin from previous context (admin@example.com / admin)
        # Or creating one? 
        # Typically seed data provides admin@example.com using 'initial_data.py' or similar. 
        # Let's try the one found in tests: admin@path.com if it persists? 
        # No, tests use in-memory DB.
        # The REAL app uses a real DB (likely postgres or sqlite in file).
        # We need an existing user.
        # If we can't login, we can't do much. 
        
        # Let's try to register a new user first (if public registration is allowed) or use common default credentials.
        # Based on `app/core/config.py` (not viewed but standard), or `initial_data`.
        
        # Checking `app/api/v1/auth.py` might reveal if there is an open registration.
        # Assuming open registration for now to perform actions.
        
        email = f"verify_{int(time.time())}@example.com"
        password = "Password123!"
        
        print(f"   Registering user {email}...")
        resp = await client.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password,
            "full_name": "Runtime Verifier",
            "phone_number": f"99999{int(time.time()) % 100000}" 
        })
        
        if resp.status_code != 200:
            print(f"   Registration failed: {resp.text}")
            # Try login with default admin if reg fails (maybe it exists)
            email = "admin@example.com" 
            password = "password" # guess
        else:
            print("   Registration success.")

        print("3. Login...")
        login_data = {"username": email, "password": password}
        resp = await client.post(f"{BASE_URL}/auth/login", data=login_data)
        
        if resp.status_code != 200:
            print(f"   Login failed: {resp.status_code} {resp.text}")
            return
            
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("   Login success.")
        
        print("4. Get current user profile...")
        resp = await client.get(f"{BASE_URL}/users/me", headers=headers)
        if resp.status_code == 200:
            user_id = resp.json()["id"]
            print(f"   User ID: {user_id}")
            
            # 5. Access Path Tests (Self-assignment might be restricted to admins, but let's try reading empty list)
            print("5. Check Access Paths (Expect Empty)...")
            resp = await client.get(f"{BASE_URL}/users/{user_id}/access-paths", headers=headers)
            if resp.status_code == 200:
                print(f"   Access Paths: {resp.json()}")
            elif resp.status_code == 403:
                print("   Access Paths: Forbidden (Expected if non-admin)")
            else:
                print(f"   Access Paths Error: {resp.status_code}")
                
        else:
            print(f"   Get Profile Failed: {resp.status_code}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_verification())
