import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "factory.db"
TRACES_DIR = BASE_DIR / "traces"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"
SERVER_PORT = 8500

# DB 설정 — DB_TYPE=oracle 로 전환 가능
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
ORACLE_DSN = os.getenv("ORACLE_DSN", "")
ORACLE_USER = os.getenv("ORACLE_USER", "")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")
