import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath('.'))

try:
    from app.workers.daily_jobs import *
    from app.workers.hourly_jobs import *
    print("Jobs imported successfully!")
except Exception as e:
    import traceback
    traceback.print_exc()

