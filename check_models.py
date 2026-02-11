import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

try:
    from app.models.warehouse import Warehouse
    from app.models.branch import Branch
    print("Models imported successfully.")
except Exception as e:
    print(f"Error importing models: {e}")
except SyntaxError as e:
    print(f"Syntax error in models: {e}")
