import sys
from pathlib import Path


# parents[1] resolves to the app root in both layouts:
#   Docker: /app/tests/conftest.py  → /app
#   Local:  api/tests/conftest.py   → api/
API_DIR = Path(__file__).resolve().parents[1]
API_SRC = API_DIR / "src"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
