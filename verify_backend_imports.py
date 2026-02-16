import sys
import os

# Add backend directory to path
sys.path.append(os.getcwd())

try:
    print("Verifying imports...")
    from app.models.station import Station
    from app.models.battery import Battery
    from app.models.rental import Rental
    from app.models.review import Review
    from app.models.favorite import Favorite
    from app.models.telematics import TelemeticsData
    from app.models.promo_code import PromoCode
    
    from app.api.v1.stations import search_nearby_stations
    from app.api.v1.rentals import initiate_rental
    from app.api.v1.batteries import scan_battery_qr
    
    from app.services.station_service import StationService
    from app.services.rental_service import RentalService
    
    print("All imports successful!")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)
