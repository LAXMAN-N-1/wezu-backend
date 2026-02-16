
import requests
import json

BASE_URL = "http://localhost:8000/api/v1/auth"

def test_register_flow():
    print("Testing Registration Flow...")
    
    # 1. Request OTP (using a random number/email to avoid conflict if possible, or just re-use)
    # Using a fake number for testing
    phone = "+919999999999" 
    
    print(f"1. Requesting OTP for {phone}...")
    try:
        req_payload = {"target": phone, "purpose": "registration"}
        resp = requests.post(f"{BASE_URL}/register/request-otp", json=req_payload)
        
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        
        if resp.status_code != 200:
            print(f"WARN: Request OTP failed ({resp.status_code}). Proceeding to verify mock...")
            # return  <-- Removed to allow step 2
    except Exception as e:
        print(f"FAILED: Connection error {e}")
        # return

    # 2. Verify OTP (mocked OTP is usually fixed or we need to know logic)
    # Assuming mock auth is enabled or we know the OTP. 
    # Earlier conversation mentioned "Integrate Mock Authentication (Mobile: 9154345918, OTP: 9640)"
    # Let's try with that specific mocked credential if the above was generic.
    
    test_phone = "+919154345918" # Mock number from task.md
    test_otp = "9640"
    
    print(f"\n2. Verifying OTP for Mock User {test_phone} with OTP {test_otp}...")
    try:
        verify_payload = {
            "target": test_phone,
            "code": test_otp,
            "purpose": "registration",
            "full_name": "Test User via Script"
        }
        resp = requests.post(f"{BASE_URL}/register/verify-otp", json=verify_payload)
        
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        
        if resp.status_code == 200:
            print("SUCCESS: User created/verified and tokens received.")
        else:
            print("FAILED: Verify OTP")

    except Exception as e:
        print(f"FAILED: Connection error {e}")

if __name__ == "__main__":
    test_register_flow()
