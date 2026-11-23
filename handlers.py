from aiogram.types import (Message , InlineQueryResultCachedAudio, InlineQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, CallbackQuery, FSInputFile , InlineQueryResultAudio)
from aiogram import Router , F
from aiogram.filters import Command, CommandStart
from urllib.parse import quote
import asyncio
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ChatAction
import logging
import downloader
import tracks_db as db
from config import ADMIN_ID, CHANNEL_ID , AUDIO_BASE_URL
from concurrent.futures import ThreadPoolExecutor
STICKER_ID = "CAACAgQAAxkBAAIBuWsEP35nQQXHMbLV7PMYQrYkj-0LAAI1HwACWdhxUCs3-Cy46P18PQQ" 
router = Router()
log = logging.getLogger(__name__)


# Сетевой поиск ( выполняется вне цикла , пока aiogram продолжает обрабатывать запросы)
search_workers = ThreadPoolExecutor(max_workers=6, thread_name_prefix="music-search")

def invalid_audio(error):
    message = str(error).upper()
    return any(code in message for code in (
        "AUDIO_CONTENT_TYPE_INVALID", "FILE_ID_INVALID", "WRONG_FILE_IDENTIFIER",
        "WRONG REMOTE FILE IDENTIFIER", "FILE_REFERENCE_EXPIRED",
        "INVALID FILE ID", "FILE_ID_EMPTY",
    ))


async def answer_cached(q, rows):
    # Успешный ответ завершает inline-запрос. После ошибки ищем первую
    # пригодную группу и помечаем только подтверждённые одиночные ошибки.
    pending = [rows] if rows else []
    for _ in range(8):
        if not pending:
            break
        group = pending.pop()
        try:
            await q.answer([
                InlineQueryResultCachedAudio(id=str(row[0]), audio_file_id=row[1])
                for row in group
            ], cache_time=30, is_personal=False)
            return True
        except TelegramBadRequest as error:
            if not invalid_audio(error):
                raise
            if len(group) == 1:
                track_id, file_id, *_ = group[0]
                db.mark_unavailable(track_id, file_id)
                log.warning("Telegram отклонил аудио для записи %s", track_id)
            else:
                middle = len(group) // 2
                pending.extend((group[middle:], group[:middle]))
    return False
async def search_source(source, query):
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(search_workers, downloader.search, source, query), 3.5,
        )
    except Exception:
        log.debug("Поиск %s недоступен", source, exc_info=True)
        return []


def search_result(track):
    uid = track["uid"]
    return InlineQueryResultAudio(
        id=uid, audio_url=f"{AUDIO_BASE_URL}/tracks/{quote(uid, safe='')}.mp3",
        title=track["title"][:256], performer=track["performer"][:256] or None,
    )
@router.message(CommandStart())
async def cmd_start(message: Message):
    log.info(f"Пользователь {message.from_user.id} (@{message.from_user.username}) запустил бота")
    await message.bot.send_chat_action(
        chat_id=message.chat.id, 
        action=ChatAction.TYPING
    )
    await asyncio.sleep(0.3)
    me = await message.bot.me() 
    await message.answer_sticker(STICKER_ID)
    await message.answer(f""" Привет! 👋 Добро пожаловать в музыкального бота.

Что я умею:
🎵 Напиши в любом чате @{me.username} и название трека
📃 /help — список команд

Просто напиши название песни — и я начну! 🚀""")
    

@router.message(Command("owner"))
async def cmd_owner(message : Message):
    await message.bot.send_chat_action(
            chat_id=message.chat.id, 
            action=ChatAction.TYPING
        )
    await asyncio.sleep(0.3)
    text = (
        "⚜️ <b>Информация о проекте.</b>\n\n"
        "<blockquote>👤 <b>Разработчик:</b> @rheophore\n"
        "📩 <b>Связь:</b> <a href='https://t.me/kiloware'>Написать в ЛС.</a></blockquote>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message : Message):
    await message.bot.send_chat_action(
            chat_id=message.chat.id, 
            action=ChatAction.TYPING
        )
    await asyncio.sleep(0.3)
    me = await message.bot.me()
    await message.answer(f"""Список команд:
🎵 @{me.username} название — поиск трека в любом чате
🎶/owner — узнать владельца бота""")


@router.message(Command("dbstat"))
async def dbstat(m: Message):
    if m.from_user.id != ADMIN_ID:
        return await m.answer("❌ У вас нет прав администратора.")
    await m.answer(f"Треков в базе: {db.count()}\nФайл: {db.DB_PATH}")

@router.inline_query()
async def inline_search(q: InlineQuery):
    query = q.query.strip()
    if not any(char.isalnum() for char in query):
        return await q.answer([], cache_time=0)

    if await answer_cached(q, db.search(query, 50)):
        return

    if not AUDIO_BASE_URL:
        return await q.answer([], cache_time=0)

    # Если кэш не помог, запрашиваем оба источника одновременно.
    batches = await asyncio.gather(
        search_source("soundcloud", query), search_source("youtube", query),
    )
    tracks = {track["uid"]: track for batch in batches for track in batch
              if db.prepare(track["title"], track["performer"])[2]}
    # HTTP-сервис находит источник по UID даже после перезапуска.
    db.save_candidates(list(tracks.values()))
    await q.answer([search_result(track) for track in tracks.values()],
                   cache_time=30 if tracks else 0)

@router.channel_post(F.audio, F.chat.id == CHANNEL_ID)
async def new_channel_track(m: Message):
    a = m.audio
    if db.add(a.file_unique_id, a.file_id, m.message_id, a.title, a.performer):
        db.commit()
    
@router.message(F.text & ~F.text.startswith('/'))
async def handle_message_search(m: Message):
    me = await m.bot.me()
    await m.answer(f"Поиск работает только через инлайн : \n\n @{me.username} название трека")
