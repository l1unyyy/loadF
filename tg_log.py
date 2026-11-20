import logging
import asyncio
from aiogram import Bot
from config import TG_TOKEN_LOG, ADMIN_ID

log_bot = Bot(TG_TOKEN_LOG)

class TelegramHandler(logging.Handler):
    def emit(self, record):
        text = self.format(record)[:4000]
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._send(text))

    async def _send(self, text):
        try :
            await log_bot.send_message(ADMIN_ID, text)
        except Exception:
            pass

def setup(logger):
    h = TelegramHandler(level = logging.WARNING)
    h.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    logger.addHandler(h)
    