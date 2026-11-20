import os
from dotenv import load_dotenv
load_dotenv()
BOT_USERNAME = "LoadfBot"
TG_TOKEN = os.getenv("TG_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = os.getenv("ADMIN_ID")