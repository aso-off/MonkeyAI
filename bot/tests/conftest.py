import sys
from pathlib import Path


# parents[1] resolves to the app root in both layouts:
#   Docker: /app/tests/conftest.py  → /app
#   Local:  bot/tests/conftest.py   → bot/
BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))
