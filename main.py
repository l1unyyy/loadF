import os
import asyncio
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
load_dotenv()
import logging
from config import BOT_USERNAME
from handlers import router
from tg_log import setup, log_bot


logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)



async def main():
    bot = Bot(os.getenv("TG_TOKEN"))
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(startup)
    dp.shutdown.register(shutdown)
    setup(logging.getLogger("handlers"))

    await bot.delete_webhook(drop_pending_updates = True) 
    await dp.start_polling(bot)
    


async def startup():
    logging.info(f"Бот {BOT_USERNAME} запущен и готов к работе")
    print("Bot started ....")

async def shutdown():
    logging.info(f"Бот {BOT_USERNAME} выключился")
    await log_bot.session.close()
    print("Bot shutting down ....")

if __name__ == "__main__":
    logging.basicConfig(level = logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")