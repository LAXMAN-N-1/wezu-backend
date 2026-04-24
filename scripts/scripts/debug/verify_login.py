"""
Debug script to verify login works.

Usage:
    python scripts/debug/verify_login.py <email> <password>
    python scripts/debug/verify_login.py                    # prompts interactively
"""
import requests
import json
import sys
import getpass

url = "http://127.0.0.1:8000/api/v1/auth/login"

email = sys.argv[1] if len(sys.argv) > 1 else input("Email: ")
password = sys.argv[2] if len(sys.argv) > 2 else getpass.getpass("Password: ")

data = {
    "username": email,
    "password": password
}
headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=data, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
