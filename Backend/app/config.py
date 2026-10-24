import os
from dotenv import load_dotenv

load_dotenv()
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
DB_PATH = os.getenv("DB_PATH", "scholarradar.db")