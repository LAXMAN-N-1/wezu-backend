import requests
import sys
import time

BASE_URL = "http://localhost:8000/api/v1/auth"
LOGIN_URL = f"{BASE_URL}/login"
LOGOUT_ALL_URL = f"{BASE_URL}/logout-all"
ME_URL = "http://localhost:8000/api/v1/users/me" 

def login():
    login_payload = {
        "username": "7778889999", 
        "password": "SecurePass123",
        "role": "customer"
    }
    response = requests.post(LOGIN_URL, json=login_payload)
    if response.status_code != 200:
        print(f"Login Failed: {response.text}")
        sys.exit(1)
    return response.json()

def verify_token(token, expect_success=True):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(ME_URL, headers=headers)
    if expect_success:
        if response.status_code == 200:
            print("  -> Token verification PASSED (Access allowed).")
            return True
        else:
            print(f"  -> Token verification FAILED (Expected success, got {response.status_code})")
            return False
    else:
        if response.status_code == 401:
            print("  -> Token verification PASSED (Access denied as expected).")
            return True
        else:
            print(f"  -> Token verification FAILED (Expected 401, got {response.status_code})")
            return False

def run_test():
    print("1. Logging in to get Token A...")
    data_a = login()
    token_a = data_a["access_token"]
    print(f"  -> Got Token A: {token_a[:10]}...")
    
    print("2. Verifying Token A works...")
    if not verify_token(token_a, expect_success=True):
        sys.exit(1)
        
    print("3. Calling /logout-all...")
    headers = {"Authorization": f"Bearer {token_a}"}
    response = requests.post(LOGOUT_ALL_URL, headers=headers)
    if response.status_code != 200:
        print(f"  -> Logout All Failed: {response.text}")
        sys.exit(1)
    print("  -> Logout All successful.")
    
    # Wait a moment to ensure timestamp difference (optional but safe)
    time.sleep(1)
    
    print("4. Verifying Token A is NOW INVALID...")
    if not verify_token(token_a, expect_success=False):
        print("FAILURE: Old token was not invalidated!")
        sys.exit(1)
        
    print("5. Logging in again to get Token B...")
    data_b = login()
    token_b = data_b["access_token"]
    print(f"  -> Got Token B: {token_b[:10]}...")
    
    print("6. Verifying Token B works...")
    if not verify_token(token_b, expect_success=True):
        print("FAILURE: New token should work!")
        sys.exit(1)
        
    print("\nSUCCESS: Logout All flow verified correctly!")

if __name__ == "__main__":
    run_test()
