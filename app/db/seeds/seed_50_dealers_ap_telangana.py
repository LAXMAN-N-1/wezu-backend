"""
Seed 50 dealers across Andhra Pradesh and Telangana for demo.
Run: python3 -m app.db.seeds.seed_50_dealers_ap_telangana
"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import re

# Load DB URL from .env
_here = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_here, '..', '..', '..', '.env')
with open(_env_path) as f:
    _env = f.read()
DATABASE_URL = re.search(r'DATABASE_URL="?([^"\n]+)"?', _env).group(1)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEALERS = [
    # Telangana - Hyderabad & surroundings
    {"business_name": "Hyderabad EV Hub", "contact_person": "Rajesh Kumar", "contact_phone": "9100000001", "email": "dealer.hyd1@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Plot 12, Banjara Hills", "pincode": "500034"},
    {"business_name": "Secunderabad Battery Zone", "contact_person": "Suresh Rao", "contact_phone": "9100000002", "email": "dealer.sec1@wezu.com", "city": "Secunderabad", "state": "Telangana", "address_line1": "45 SP Road", "pincode": "500003"},
    {"business_name": "Madhapur EV Station", "contact_person": "Priya Sharma", "contact_phone": "9100000003", "email": "dealer.madhapur@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Cyber Towers, Madhapur", "pincode": "500081"},
    {"business_name": "Kondapur Power Hub", "contact_person": "Venkat Reddy", "contact_phone": "9100000004", "email": "dealer.kondapur@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Survey No 45, Kondapur", "pincode": "500084"},
    {"business_name": "Gachibowli EV Store", "contact_person": "Anand Singh", "contact_phone": "9100000005", "email": "dealer.gach@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "DLF Cyber City, Gachibowli", "pincode": "500032"},
    {"business_name": "LB Nagar Battery Point", "contact_person": "Lakshmi Devi", "contact_phone": "9100000006", "email": "dealer.lbnagar@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Main Road, LB Nagar", "pincode": "500074"},
    {"business_name": "Dilsukhnagar EV Center", "contact_person": "Mohammed Ali", "contact_phone": "9100000007", "email": "dealer.dilsukh@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Dilsukhnagar Main Rd", "pincode": "500060"},
    {"business_name": "Kukatpally Energy Hub", "contact_person": "Ravi Teja", "contact_phone": "9100000008", "email": "dealer.kuka@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "KPHB Colony, Kukatpally", "pincode": "500072"},
    {"business_name": "Ameerpet Power Station", "contact_person": "Srinivas Murthy", "contact_phone": "9100000009", "email": "dealer.ameer@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Metro Pillar 67, Ameerpet", "pincode": "500016"},
    {"business_name": "Uppal EV Solutions", "contact_person": "Kishore Babu", "contact_phone": "9100000010", "email": "dealer.uppal@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Uppal Ring Road", "pincode": "500039"},
    # Telangana - Other cities
    {"business_name": "Warangal EV Hub", "contact_person": "Ramesh Nayak", "contact_phone": "9100000011", "email": "dealer.warangal@wezu.com", "city": "Warangal", "state": "Telangana", "address_line1": "Hanamkonda Road, Warangal", "pincode": "506001"},
    {"business_name": "Karimnagar Battery Store", "contact_person": "Naveen Kumar", "contact_phone": "9100000012", "email": "dealer.karimnagar@wezu.com", "city": "Karimnagar", "state": "Telangana", "address_line1": "Manakondur Road", "pincode": "505001"},
    {"business_name": "Nizamabad EV Point", "contact_person": "Deepak Reddy", "contact_phone": "9100000013", "email": "dealer.nizamabad@wezu.com", "city": "Nizamabad", "state": "Telangana", "address_line1": "Armoor Road, Nizamabad", "pincode": "503001"},
    {"business_name": "Khammam Power Center", "contact_person": "Satish Kumar", "contact_phone": "9100000014", "email": "dealer.khammam@wezu.com", "city": "Khammam", "state": "Telangana", "address_line1": "Wyra Road, Khammam", "pincode": "507001"},
    {"business_name": "Nalgonda EV Station", "contact_person": "Srikanth Rao", "contact_phone": "9100000015", "email": "dealer.nalgonda@wezu.com", "city": "Nalgonda", "state": "Telangana", "address_line1": "Miryalguda Road", "pincode": "508001"},
    {"business_name": "Mahbubnagar EV Hub", "contact_person": "Prasad Reddy", "contact_phone": "9100000016", "email": "dealer.mahbub@wezu.com", "city": "Mahbubnagar", "state": "Telangana", "address_line1": "Jadcherla Road", "pincode": "509001"},
    {"business_name": "Adilabad Battery Zone", "contact_person": "Arun Teja", "contact_phone": "9100000017", "email": "dealer.adilabad@wezu.com", "city": "Adilabad", "state": "Telangana", "address_line1": "Nirmal Road, Adilabad", "pincode": "504001"},
    {"business_name": "Medak EV Solutions", "contact_person": "Kiran Kumar", "contact_phone": "9100000018", "email": "dealer.medak@wezu.com", "city": "Medak", "state": "Telangana", "address_line1": "Zaheerabad Road", "pincode": "502110"},
    {"business_name": "Siddipet Power Hub", "contact_person": "Sudarshan Rao", "contact_phone": "9100000019", "email": "dealer.siddipet@wezu.com", "city": "Siddipet", "state": "Telangana", "address_line1": "Gajwel Road, Siddipet", "pincode": "502103"},
    {"business_name": "Sangareddy EV Center", "contact_person": "Raju Sharma", "contact_phone": "9100000020", "email": "dealer.sangareddy@wezu.com", "city": "Sangareddy", "state": "Telangana", "address_line1": "Patancheru Road", "pincode": "502001"},
    # Andhra Pradesh - Vijayawada & surroundings
    {"business_name": "Vijayawada EV Hub", "contact_person": "Krishna Prasad", "contact_phone": "9100000021", "email": "dealer.vjw1@wezu.com", "city": "Vijayawada", "state": "Andhra Pradesh", "address_line1": "Eluru Road, Benz Circle", "pincode": "520001"},
    {"business_name": "Guntur Battery Store", "contact_person": "Nagabhushanam", "contact_phone": "9100000022", "email": "dealer.guntur@wezu.com", "city": "Guntur", "state": "Andhra Pradesh", "address_line1": "Arundelpet Main Road", "pincode": "522002"},
    {"business_name": "Nellore EV Station", "contact_person": "Subba Rao", "contact_phone": "9100000023", "email": "dealer.nellore@wezu.com", "city": "Nellore", "state": "Andhra Pradesh", "address_line1": "Pogathota Road", "pincode": "524001"},
    {"business_name": "Visakhapatnam Power Hub", "contact_person": "Venu Gopal", "contact_phone": "9100000024", "email": "dealer.vizag1@wezu.com", "city": "Visakhapatnam", "state": "Andhra Pradesh", "address_line1": "Dwaraka Nagar", "pincode": "530016"},
    {"business_name": "Vizag Steel City EV", "contact_person": "Harish Babu", "contact_phone": "9100000025", "email": "dealer.vizag2@wezu.com", "city": "Visakhapatnam", "state": "Andhra Pradesh", "address_line1": "MVP Colony", "pincode": "530017"},
    {"business_name": "Kurnool EV Solutions", "contact_person": "Ramana Reddy", "contact_phone": "9100000026", "email": "dealer.kurnool@wezu.com", "city": "Kurnool", "state": "Andhra Pradesh", "address_line1": "Bellary Road, Kurnool", "pincode": "518001"},
    {"business_name": "Kakinada Battery Zone", "contact_person": "Satyam Raju", "contact_phone": "9100000027", "email": "dealer.kakinada@wezu.com", "city": "Kakinada", "state": "Andhra Pradesh", "address_line1": "Main Road, Kakinada", "pincode": "533001"},
    {"business_name": "Rajahmundry EV Center", "contact_person": "Chalapathi Rao", "contact_phone": "9100000028", "email": "dealer.rajam@wezu.com", "city": "Rajahmundry", "state": "Andhra Pradesh", "address_line1": "In Front of RTC Complex", "pincode": "533101"},
    {"business_name": "Tirupati EV Station", "contact_person": "Balaji Reddy", "contact_phone": "9100000029", "email": "dealer.tirupati@wezu.com", "city": "Tirupati", "state": "Andhra Pradesh", "address_line1": "Balaji Nagar, Tirupati", "pincode": "517501"},
    {"business_name": "Anantapur Power Hub", "contact_person": "Prabhakar Rao", "contact_phone": "9100000030", "email": "dealer.anantapur@wezu.com", "city": "Anantapur", "state": "Andhra Pradesh", "address_line1": "Tadipatri Road", "pincode": "515001"},
    # AP - More cities
    {"business_name": "Chittoor EV Hub", "contact_person": "Siva Reddy", "contact_phone": "9100000031", "email": "dealer.chittoor@wezu.com", "city": "Chittoor", "state": "Andhra Pradesh", "address_line1": "Vellore Road, Chittoor", "pincode": "517001"},
    {"business_name": "Ongole Battery Center", "contact_person": "Mallikarjuna", "contact_phone": "9100000032", "email": "dealer.ongole@wezu.com", "city": "Ongole", "state": "Andhra Pradesh", "address_line1": "Trunk Road, Ongole", "pincode": "523001"},
    {"business_name": "Eluru EV Solutions", "contact_person": "Suresh Babu", "contact_phone": "9100000033", "email": "dealer.eluru@wezu.com", "city": "Eluru", "state": "Andhra Pradesh", "address_line1": "Bandar Road, Eluru", "pincode": "534001"},
    {"business_name": "Machilipatnam Power Zone", "contact_person": "Bhaskar Rao", "contact_phone": "9100000034", "email": "dealer.machili@wezu.com", "city": "Machilipatnam", "state": "Andhra Pradesh", "address_line1": "RR Nagar", "pincode": "521001"},
    {"business_name": "Bhimavaram EV Hub", "contact_person": "Mohan Krishna", "contact_phone": "9100000035", "email": "dealer.bhimavaram@wezu.com", "city": "Bhimavaram", "state": "Andhra Pradesh", "address_line1": "Tanuku Road", "pincode": "534201"},
    {"business_name": "Tadepalligudem Battery Store", "contact_person": "Nageswara Rao", "contact_phone": "9100000036", "email": "dealer.tadep@wezu.com", "city": "Tadepalligudem", "state": "Andhra Pradesh", "address_line1": "Eluru Road", "pincode": "534101"},
    {"business_name": "Vizianagaram EV Center", "contact_person": "Appala Raju", "contact_phone": "9100000037", "email": "dealer.vizianagaram@wezu.com", "city": "Vizianagaram", "state": "Andhra Pradesh", "address_line1": "Balaji Nagar", "pincode": "535001"},
    {"business_name": "Srikakulam Power Station", "contact_person": "Murali Krishna", "contact_phone": "9100000038", "email": "dealer.srikak@wezu.com", "city": "Srikakulam", "state": "Andhra Pradesh", "address_line1": "Gandhi Nagar", "pincode": "532001"},
    {"business_name": "Kadapa EV Hub", "contact_person": "Obulaiah Reddy", "contact_phone": "9100000039", "email": "dealer.kadapa@wezu.com", "city": "Kadapa", "state": "Andhra Pradesh", "address_line1": "Trunk Road, Kadapa", "pincode": "516001"},
    {"business_name": "Nandyal Battery Zone", "contact_person": "Srinivasa Reddy", "contact_phone": "9100000040", "email": "dealer.nandyal@wezu.com", "city": "Nandyal", "state": "Andhra Pradesh", "address_line1": "Allagadda Road", "pincode": "518501"},
    # More Telangana urban
    {"business_name": "Miyapur EV Point", "contact_person": "Santosh Kumar", "contact_phone": "9100000041", "email": "dealer.miyapur@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Miyapur Main Road", "pincode": "500049"},
    {"business_name": "Alwal Battery Hub", "contact_person": "Ramachandar", "contact_phone": "9100000042", "email": "dealer.alwal@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Alwal Main Road", "pincode": "500010"},
    {"business_name": "Champapet EV Store", "contact_person": "Narender Rao", "contact_phone": "9100000043", "email": "dealer.champapet@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Champapet X Roads", "pincode": "500079"},
    {"business_name": "Nacharam Power Hub", "contact_person": "Vijay Kumar", "contact_phone": "9100000044", "email": "dealer.nacharam@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "IDA Nacharam", "pincode": "500076"},
    {"business_name": "Hayathnagar EV Center", "contact_person": "Sreedhar Rao", "contact_phone": "9100000045", "email": "dealer.hayath@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Hayathnagar Main Road", "pincode": "501505"},
    {"business_name": "Medchal EV Station", "contact_person": "Gopala Krishna", "contact_phone": "9100000046", "email": "dealer.medchal@wezu.com", "city": "Medchal", "state": "Telangana", "address_line1": "NH44 Medchal", "pincode": "501401"},
    {"business_name": "Ghatkesar Battery Point", "contact_person": "Ramaiah Nayak", "contact_phone": "9100000047", "email": "dealer.ghatkesar@wezu.com", "city": "Ghatkesar", "state": "Telangana", "address_line1": "Ghatkesar Road", "pincode": "501301"},
    {"business_name": "Shamshabad EV Hub", "contact_person": "Manjunath Rao", "contact_phone": "9100000048", "email": "dealer.shamshabad@wezu.com", "city": "Hyderabad", "state": "Telangana", "address_line1": "Airport Road, Shamshabad", "pincode": "501218"},
    {"business_name": "Patancheru Power Store", "contact_person": "Amarendra Babu", "contact_phone": "9100000049", "email": "dealer.patancheru@wezu.com", "city": "Sangareddy", "state": "Telangana", "address_line1": "IDA Patancheru", "pincode": "502319"},
    {"business_name": "Suryapet EV Solutions", "contact_person": "Chandramouli", "contact_phone": "9100000050", "email": "dealer.suryapet@wezu.com", "city": "Suryapet", "state": "Telangana", "address_line1": "Miryalaguda Road", "pincode": "508213"},
]


def seed_dealers():
    engine = create_engine(DATABASE_URL)
    hashed_password = pwd_context.hash("Dealer@123")

    # Get dealer role id once
    with engine.connect() as conn:
        dealer_role_id = conn.execute(
            text("SELECT id FROM roles WHERE LOWER(name) = 'dealer' ORDER BY id LIMIT 1")
        ).scalar()

    created = 0
    skipped = 0
    errors = 0

    for d in DEALERS:
        # Each dealer in its own connection/transaction
        try:
            with engine.begin() as conn:
                # Check if already exists
                exists = conn.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": d["email"]}
                ).scalar()

                if exists:
                    skipped += 1
                    continue

                # Create user
                user_id = conn.execute(text("""
                    INSERT INTO users (
                        email, full_name, hashed_password, user_type, status,
                        is_superuser, is_deleted, two_factor_enabled, biometric_login_enabled,
                        kyc_status, role_id, failed_login_attempts, force_password_change,
                        created_at, updated_at
                    ) VALUES (
                        :email, :full_name, :hashed_password, 'DEALER', 'ACTIVE',
                        false, false, false, false,
                        'NOT_SUBMITTED', :role_id, 0, false,
                        NOW(), NOW()
                    ) RETURNING id
                """), {
                    "email": d["email"],
                    "full_name": d["contact_person"],
                    "hashed_password": hashed_password,
                    "role_id": dealer_role_id,
                }).scalar()

                # Create dealer profile
                dp_id = conn.execute(text("""
                    INSERT INTO dealer_profiles (
                        user_id, business_name, contact_person, contact_email,
                        contact_phone, address_line1, city, state, pincode, is_active,
                        created_at
                    ) VALUES (
                        :user_id, :business_name, :contact_person, :email,
                        :contact_phone, :address_line1, :city, :state, :pincode, true,
                        NOW()
                    ) RETURNING id
                """), {
                    "user_id": user_id,
                    "business_name": d["business_name"],
                    "contact_person": d["contact_person"],
                    "email": d["email"],
                    "contact_phone": d["contact_phone"],
                    "address_line1": d["address_line1"],
                    "city": d["city"],
                    "state": d["state"],
                    "pincode": d["pincode"],
                }).scalar()

                # Create dealer application record
                conn.execute(text("""
                    INSERT INTO dealer_applications (dealer_id, current_stage, risk_score, status_history, created_at, updated_at)
                    VALUES (:dp_id, 'APPROVED', 0, '[]'::jsonb, NOW(), NOW())
                """), {"dp_id": dp_id})

            created += 1
            if created % 10 == 0:
                print(f"  Created {created} dealers...")

        except Exception as e:
            errors += 1
            print(f"  ERROR for {d['email']}: {e}")

    print(f"\nDone! Created: {created}, Skipped: {skipped}, Errors: {errors}")

    # Print summary
    with engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM dealer_profiles")).scalar()
        print(f"Total dealer_profiles in DB: {total}")


if __name__ == "__main__":
    print("Seeding 50 dealers across Andhra Pradesh and Telangana...")
    seed_dealers()
