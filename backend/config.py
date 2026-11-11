"""
Configuration settings for ProofLedger Backend Service.
Decoupled from AI research/training scripts.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure the root, backend, ai, and ai/src directories are on the python path
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
AI_DIR = ROOT_DIR / "ai"

if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(AI_DIR / "src") not in sys.path:
    sys.path.insert(0, str(AI_DIR / "src"))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load .env from root or ai/.env
env_file = ROOT_DIR / ".env"
if not env_file.exists():
    env_file = AI_DIR / ".env"
load_dotenv(env_file)

# Canonical Data Paths
DATA_DIR = AI_DIR / "data"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "proofledger.db"))).resolve()
V2_CHAIN_LOG_PATH = Path(os.getenv("CHAIN_LOG_PATH", str(DATA_DIR / "events_hash_chain_v2.jsonl"))).resolve()
V2_MANIFEST_PATH = Path(str(V2_CHAIN_LOG_PATH) + ".manifest.json").resolve()
LEGACY_CHAIN_LOG_PATH = Path(str(DATA_DIR / "events_hash_chain.jsonl")).resolve()
LEGACY_ARCHIVE_PATH = Path(str(DATA_DIR / "events_hash_chain_legacy_archive.jsonl")).resolve()
LOCK_PATH = Path(str(V2_CHAIN_LOG_PATH) + ".lock").resolve()
CHECKPOINTS_DIR = Path(str(DATA_DIR / "checkpoints")).resolve()

# Security & Signing Keys (Zero hardcoded secrets in source code)
DEFAULT_SIGNING_KEY_ID = os.getenv("PROOFLEDGER_KEY_ID", "v1-sandbox-202610")
DEFAULT_SIGNING_KEY = os.getenv("PROOFLEDGER_SIGNING_KEY", None)

# Environment & Operational Governance
def is_production_mode() -> bool:
    """Check dynamically whether the application is running in production mode."""
    return os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).strip().lower() == "production"

def should_seed_demo_credentials() -> bool:
    """Check dynamically whether demo credentials should be active."""
    if is_production_mode():
        return False
    val = os.getenv("SEED_DEMO_CREDENTIALS")
    if val is not None:
        return val.strip().lower() in ("true", "1", "yes")
    return not is_production_mode()

APP_ENV = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
SEED_DEMO_CREDENTIALS = should_seed_demo_credentials()

# PayPal Sandbox References
SANDBOX_ORDER_ID = "3EU95140LR696653G"
SANDBOX_CAPTURE_ID = "10A71705XW788203L"
SANDBOX_AMOUNT = "5.00"
SANDBOX_CURRENCY = "USD"

