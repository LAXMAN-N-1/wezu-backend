import traceback
import sys
import os

print("--- Current Working Directory ---")
print(os.getcwd())
print("--- Python Path ---")
print(sys.path)

print("--- Attempting Import ---")
try:
    from app.main import app
    print("Success: App imported successfully!")
except ImportError as e:
    print(f"ImportError caught: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"General Exception caught: {e}")
    traceback.print_exc()
