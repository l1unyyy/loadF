import os
from dotenv import load_dotenv
load_dotenv()
BOT_USERNAME = os.getenv("BOT_USERNAME")
TG_TOKEN = os.getenv("TG_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
TG_TOKEN_LOG = os.getenv("TG_TOKEN_LOG")

if not TG_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")

if not TG_TOKEN_LOG:
    raise ValueError("BOT_TOKEN для логов не задан в .env")


AUDIO_BASE_URL = os.getenv("AUDIO_BASE_URL", "").strip().rstrip("/")
AUDIO_PORT = int(os.getenv("AUDIO_PORT", "8080"))
if AUDIO_BASE_URL and not AUDIO_BASE_URL.startswith("https://"):
    raise ValueError("AUDIO_BASE_URL должен начинаться с https://")