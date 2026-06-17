import os

from dotenv import load_dotenv

load_dotenv()

GLPI_API_BASE_URL = os.environ["GLPI_API_BASE_URL"].rstrip("/")
GLPI_OAUTH_CLIENT_ID = os.environ["GLPI_OAUTH_CLIENT_ID"]
GLPI_OAUTH_CLIENT_SECRET = os.environ["GLPI_OAUTH_CLIENT_SECRET"]
GLPI_BOT_USERNAME = os.environ["GLPI_BOT_USERNAME"]
GLPI_BOT_PASSWORD = os.environ["GLPI_BOT_PASSWORD"]
SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "60"))

OLLAMA_API_URL = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")

DATABASE_URL = os.environ["DATABASE_URL"]
