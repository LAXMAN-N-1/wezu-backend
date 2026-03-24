
import requests

r1 = requests.get('http://127.0.0.1:8000/api/v1/catalog/products')
print('ALL:', r1.json())

r2 = requests.get('http://127.0.0.1:8000/api/v1/catalog/products?category=EV+Battery')
print('EV Battery:', r2.json())

