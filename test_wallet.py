import requests
import json

base_url = "http://localhost:8000/api/v1"
auth_url = f"{base_url}/customer/auth/login"
print("Attempting login...")
try:
    res = requests.post(auth_url, json={"phone": "9154345918"})
    print("Login:", res.status_code)
    token = res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Fetching cashback...")
    res2 = requests.get(f"{base_url}/wallet/cashback", headers=headers)
    print("Cashback status:", res2.status_code)
    print("Cashback text:", res2.text)
except Exception as e:
    print("Error:", e)
