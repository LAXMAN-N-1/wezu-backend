import requests
import json

base_url = "http://localhost:8000/api/v1"
auth_url = f"{base_url}/customer/auth/login"

print("--- End to End Verification ---")
try:
    print("1. Logging in...")
    res = requests.post(auth_url, json={"phone": "9154345918"})
    res.raise_for_status()
    token = res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n2. Verifying Wallet Cashback History...")
    res2 = requests.get(f"{base_url}/wallet/transactions", headers=headers)
    print("Wallet Transactions Status:", res2.status_code)
    
    print("\n3. Verifying Subscription Plans (No double slash!)...")
    res3 = requests.get(f"{base_url}/subscriptions/plans", headers=headers)
    print("Subscriptions Status:", res3.status_code)
    print("Num Plans:", len(res3.json().get('data', [])) if res3.status_code == 200 else res3.text)
    
    print("\n4. Verifying Map Stations...")
    res4 = requests.get(f"{base_url}/stations/nearby?lat=17.488&lon=78.415&radius=5.0", headers=headers)
    stations_data = res4.json().get('data', [])
    print("Nearby Stations Status:", res4.status_code)
    print("Nearby Stations Count:", len(stations_data))
    
    print("\n5. Verifying Shop Sorting...")
    res5 = requests.get(f"{base_url}/catalog/products/search?sortBy=price_asc", headers=headers)
    print("Shop Sort Status:", res5.status_code)
    products = res5.json().get('data', {}).get('items', [])
    print("Sorted Products length:", len(products))
    if len(products) >= 2:
        print(f"First price: {products[0]['price']}, Second price: {products[1]['price']}")

except Exception as e:
    print("Error:", e)
