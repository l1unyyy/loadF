from aiogram.exceptions import (TelegramBadRequest, TelegramForbiddenError,
                                TelegramNetworkError, TelegramRetryAfter,
                                TelegramServerError)
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram import Bot
from config import TG_TOKEN, CHANNEL_ID, ADMIN_ID
import config
import tracks_db as db
import asyncio
import os
import sys

POS_FILE = "import_pos.txt"

if "--reset" in sys.argv:
    for f in ("tracks.db", "tracks.db-wal", "tracks.db-shm", POS_FILE):
        if os.path.exists(f):
            os.remove(f)

PROXY = getattr(config, "PROXY", None)


args = [a for a in sys.argv[1:] if a.isdigit()]
LAST_ID = int(args[0]) if args else int(input("id последнего поста в канале : "))
start = int(open(POS_FILE).read()) + 1 if os.path.exists(POS_FILE) else 1

async def retry(make_call):
    delay = 3
    while True:
        try:
            return await make_call()
        except TelegramRetryAfter as e:
            print(f"лимит Телеграма, жду {e.retry_after} сек", flush=True)
            await asyncio.sleep(e.retry_after + 1)
        except (TelegramNetworkError, TelegramServerError, asyncio.TimeoutError):
            print(f"нет связи с Телеграмом, повтор через {delay} сек…", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)



async def main():
    session = AiohttpSession(proxy=PROXY) if PROXY else AiohttpSession()
    bot = Bot(TG_TOKEN, session=session)
    added = dupes = 0
    done = start - 1                      # последний полностью обработанный пост
    try:
        for mid in range(start, LAST_ID + 1):
            m = None
            try:
                m = await retry(lambda: bot.forward_message(ADMIN_ID, CHANNEL_ID, mid))
            except TelegramBadRequest:
                pass                      # поста нет (удалён) или его нельзя переслать
            except TelegramForbiddenError:
                print("Бот не может писать админу: напиши боту /start с аккаунта ADMIN_ID")
                return
            if m:
                a = m.audio
                if a:
                    if db.add(a.file_unique_id, a.file_id, mid, a.title, a.performer):
                        added += 1
                    else:
                        dupes += 1
                try:
                    await retry(lambda: bot.delete_message(ADMIN_ID, m.message_id))
                except TelegramBadRequest:
                    pass
                await asyncio.sleep(0.5)
            done = mid
            if mid % 100 == 0:
                db.commit()
                open(POS_FILE, "w").write(str(done))
                print(f"пост {mid}/{LAST_ID} | добавлено {added} | дублей {dupes}", flush=True)
        print(f"готово: добавлено {added}, дублей пропущено {dupes}")
    finally:
        db.commit()                       # прогресс сохранится и при Ctrl+C, и при ошибке
        open(POS_FILE, "w").write(str(done))
        await bot.session.close()


asyncio.run(main())