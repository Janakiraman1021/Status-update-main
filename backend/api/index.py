import sys
from pathlib import Path

# Add backend directory to sys.path so app and run can be imported reliably
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from run import app
