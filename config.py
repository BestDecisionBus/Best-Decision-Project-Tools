import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "bdb_tools.db"
RECEIPTS_DIR = BASE_DIR / "receipts"
JOB_PHOTOS_DIR = BASE_DIR / "job_photos"
EXPORTS_DIR = BASE_DIR / "exports"
LOGOS_DIR = BASE_DIR / "static" / "logos"
ESTIMATES_VAULT = BASE_DIR / "estimates"

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
VIEWER_USERNAME = os.getenv("VIEWER_USERNAME", "viewer")
VIEWER_PASSWORD = os.getenv("VIEWER_PASSWORD", "viewer")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "60"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "30"))

# GPS validation: max distance (miles) between punch and job before flagging
GPS_FLAG_DISTANCE_MILES = float(os.getenv("GPS_FLAG_DISTANCE_MILES", "0.5"))

# Ollama (local LLM for task extraction)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

# Ensure directories exist on import
INSTANCE_DIR.mkdir(exist_ok=True)
RECEIPTS_DIR.mkdir(exist_ok=True)
JOB_PHOTOS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)
LOGOS_DIR.mkdir(exist_ok=True, parents=True)
ESTIMATES_VAULT.mkdir(exist_ok=True)
