import os
from dotenv import load_dotenv
load_dotenv()
BOT_USERNAME = os.getenv("BOT_USERNAME")
TG_TOKEN = os.getenv("TG_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TG_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")
