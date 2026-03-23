import os
import sys

# We are in backend
sys.path.insert(0, os.path.abspath("."))

from app.db.session import get_session
from app.models.battery import Battery
from sqlmodel import select

try:
    db = next(get_session())
    print("Executing query...")
    batteries = db.exec(select(Battery).limit(1)).all()
    print(f"Success! Found {len(batteries)} batteries.")
except Exception as e:
    import traceback
    traceback.print_exc()
