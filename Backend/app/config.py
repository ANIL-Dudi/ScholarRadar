
import os
from pathlib import Path

from dotenv import load_dotenv

# Backend directory: ScholarRadar/Backend
BASE_DIR = Path(__file__).resolve().parents[1]

# Load environment variables from Backend/.env
load_dotenv(BASE_DIR / ".env")

TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6").strip()

_db_path = Path(os.getenv("DB_PATH", "scholarradar.db"))
DB_PATH = str(
    _db_path if _db_path.is_absolute() else BASE_DIR / _db_path
)
