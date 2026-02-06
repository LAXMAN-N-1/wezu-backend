import requests
import sys

BASE_URL = "http://localhost:8000/api/v1/auth"
LOGIN_URL = f"{BASE_URL}/login"
REFRESH_URL = f"{BASE_URL}/refresh"

def verify_refresh_flow():
    # 1. Login to get initial tokens
    print(f"Logging in to {LOGIN_URL}...")
    login_payload = {
        "username": "7778889999", 
        "password": "SecurePass123",
        "role": "customer"
    }
    
    try:
        response = requests.post(LOGIN_URL, json=login_payload)
        response.raise_for_status()
        data = response.json()
        
        initial_access = data.get("access_token")
        initial_refresh = data.get("refresh_token")
        
        if not initial_refresh:
            print("FAILED: No refresh token returned in login response")
            sys.exit(1)
            
        print(f"Login Success. Refresh Token: {initial_refresh[:10]}...")
        
        # 2. Call Refresh Endpoint
        print(f"Calling Refresh Endpoint: {REFRESH_URL}...")
        refresh_payload = {
            "refresh_token": initial_refresh
        }
        
        refresh_response = requests.post(REFRESH_URL, json=refresh_payload)
        if refresh_response.status_code != 200:
            print(f"FAILED: Refresh call returned {refresh_response.status_code}")
            print(refresh_response.text)
            sys.exit(1)
            
        refresh_data = refresh_response.json()
        new_access = refresh_data.get("access_token")
        new_refresh = refresh_data.get("refresh_token")
        
        if not new_access or not new_refresh:
             print("FAILED: New tokens not found in refresh response")
             sys.exit(1)
             
        if new_refresh == initial_refresh:
            print("WARNING: Refresh token was NOT rotated (Same token returned)")
        else:
            print("SUCCESS: Refresh token was rotated.")
            
        print("Refresh Token Verification Passed!")
        print(f"New Access Token: {new_access[:10]}...")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_refresh_flow()
