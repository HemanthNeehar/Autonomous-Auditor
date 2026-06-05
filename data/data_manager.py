# =========================================================================
#  DATA LOADING
# =========================================================================
import os
import sys
import json
from pathlib import Path

# --- Path Setup ---
SRC_DIR = Path(__file__).resolve().parent.parent
print(SRC_DIR, "\n")
sys.path.insert(0, str(SRC_DIR))

CUSTOMER_DB: list[dict] = []
ORDER_DB: list[dict] = []
CUSTOMER_ID_SET: set[str] = set()
REGULATION_TEXT: str = ""

def load_data():
    """Load JSON databases and regulation file into memory."""
    global CUSTOMER_DB, ORDER_DB, CUSTOMER_ID_SET, REGULATION_TEXT
    try:
        with open(SRC_DIR / "customer_db.json", "r") as f:
            CUSTOMER_DB = json.load(f)
        with open(SRC_DIR / "orders_db.json", "r") as f:
            ORDER_DB = json.load(f)
        CUSTOMER_ID_SET = set(c["customer_id"] for c in CUSTOMER_DB)
        with open(SRC_DIR / "regulation.txt", "r") as f:
            REGULATION_TEXT = f.read()
        print(f"✓ Loaded {len(CUSTOMER_DB)} customers, {len(ORDER_DB)} orders")
    except FileNotFoundError as e:
        print(f"ERROR: Data file not found: {e}")

load_data()