import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

GROQ_API_KEY = os.environ["GROQ_API_KEY"]

ORACLE_HOST = os.environ["ORACLE_HOST"]
ORACLE_PORT = int(os.environ.get("ORACLE_PORT", "1521"))
ORACLE_SERVICE_NAME = os.environ["ORACLE_SERVICE_NAME"]

ORACLE_USER = os.environ["ORACLE_USER"]
ORACLE_PASSWORD = os.environ["ORACLE_PASSWORD"]

ORACLE_DATA_OWNER_SCHEMA = os.environ[
    "ORACLE_DATA_OWNER_SCHEMA"
].upper()

ORACLE_DSN = (
    f"{ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE_NAME}"
)