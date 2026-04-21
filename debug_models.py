import sys
import os
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from app.models.all import *
    print("Successfully imported all models!")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
