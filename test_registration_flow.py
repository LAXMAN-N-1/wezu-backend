import httpx
import asyncio
import time

async def simulate_registration_flow():
    base_url = "http://localhost:8011/api/v1/customer"
    phone = "9112223388"
    password = "MySecurePassword123"
    name = "Flow Test User"
    
    print("\n--- SIMULATING APP REGISTRATION FLOW ---")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # STEP 1: Click Continue on Registration Screen
        print(f"\n1. Clicked Continue. POST /auth/register...")
        start = time.time()
        reg_resp = await client.post(f"{base_url}/auth/register", json={
            "phone_number": phone,
            "password": password,
            "full_name": name
        })
        print(f"   Status: {reg_resp.status_code}")
        print(f"   Time taken: {time.time() - start:.2f}s")
        if reg_resp.status_code != 200:
            print(f"   Failed! {reg_resp.text}")
            return
            
        print("   User successfully created in DB!")
        
        # STEP 2: Frontend automatically requests OTP
        print(f"\n2. Automatic OTP Request. POST /auth/register/request-otp...")
        start = time.time()
        otp_resp = await client.post(f"{base_url}/auth/register/request-otp", json={
            "target": phone,
            "purpose": "registration"
        })
        print(f"   Status: {otp_resp.status_code}")
        print(f"   Time taken: {time.time() - start:.2f}s")
        if otp_resp.status_code != 200:
            print(f"   Failed! {otp_resp.text}")
            return
            
        print("   OTP Requested successfully!")
        
        # STEP 3: User enters OTP on next screen
        print(f"\n3. User enters OTP. POST /auth/register/verify-otp...")
        start = time.time()
        verify_resp = await client.post(f"{base_url}/auth/register/verify-otp", json={
            "target": phone,
            "code": "964056",
            "purpose": "registration",
            "full_name": name
        })
        print(f"   Status: {verify_resp.status_code}")
        print(f"   Time taken: {time.time() - start:.2f}s")
        if verify_resp.status_code != 200:
            print(f"   Failed! {verify_resp.text}")
            return
            
        data = verify_resp.json()
        print(f"   Success! Logged in. Token received: {data.get('access_token')[:20]}...")
        
        # STEP 4: User attempts to login mapping password directly
        print(f"\n4. VERIFICATION: Can User Login with Password? POST /auth/login...")
        start = time.time()
        login_resp = await client.post(f"{base_url}/auth/login", data={
            "username": phone,
            "password": password
        })
        print(f"   Status: {login_resp.status_code}")
        print(f"   Time taken: {time.time() - start:.2f}s")
        if login_resp.status_code != 200:
            print(f"   Failed to login with password! Password was NOT stored correctly!")
            print(f"   Response: {login_resp.text}")
        else:
            print(f"   Login successful! Password was stored and hashed correctly.")

if __name__ == "__main__":
    asyncio.run(simulate_registration_flow())
