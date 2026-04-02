import os
import requests

def test_login():
    url = "http://localhost:8000/api/v1/customer/auth/login"
    payload = {
        "email": "9154345918",
        "password": os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe!Seed2026")
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        if response.status_code == 200:
            print("Login successful!")
        else:
            print("Login failed!")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_login()
