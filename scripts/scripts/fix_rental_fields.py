import os

files_to_fix = [
    "app/services/analytics/dealer_service.py",
    "app/services/admin_analytics_service.py",
    "app/services/ml_fraud_service.py",
    "app/services/rental_service.py",
    "app/api/v1/rentals.py",
    "app/schemas/rental.py",
    "app/db/seeds/seed_analytics.py"
]

for filepath in files_to_fix:
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            content = f.read()
        
        # Replacements
        content = content.replace("pickup_station_id", "start_station_id")
        content = content.replace("Rental.total_price", "Rental.total_amount")
        
        if "schemas/rental.py" in filepath:
            content = content.replace("total_price: float", "total_amount: float")
        
        if "seed_analytics.py" in filepath:
            content = content.replace("total_price=", "total_amount=")
            content = content.replace("total_price =", "total_amount =")
            
        with open(filepath, "w") as f:
            f.write(content)

print("Mass replacement complete.")
