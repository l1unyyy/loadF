import os
import asyncio
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv




dp = Dispatcher()

async def main():
    load_dotenv()
    bot = Bot(os.getenv("TG_TOKEN"))
    dp.startup.register(startup)
    dp.shutdown.register(shutdown)
    await bot.delete_webhook(drop_pending_updates = True) 
    await dp.start_polling(bot)



async def startup():
    print("Bot started ....")

async def shutdown():
    print("Bot shutting down ....")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")