from aiogram.types import Message, InlineQueryResultCachedAudio, InlineQueryResultAudio, InlineQuery
from urllib.parse import quote
from aiogram import Router , F
from aiogram.filters import Command, CommandStart
import asyncio
from concurrent.futures import ThreadPoolExecutor
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ChatAction
import logging
import downloader
import tracks_db as db
from config import ADMIN_ID, AUDIO_BASE_URL, CHANNEL_ID

emoji_github = "5314703247737376876"
emoji_dev = "5818813162815753343"
emoji_user = "5985378660343877179"
emoji_diamond = "6012666146648495705"
emoji_message = "5253742260054409879"
emoji_music = "5222472119295684375"
emoji_pods = "6021638234545592807"
emoji_info = "5352667722092139468"
emoji_python = "5404355553260480491"
emoji_rocket = "5372917041193828849"
emoji_hello = "5251678365059931202"

STICKER_ID = "CAACAgQAAxkBAAIBuWsEP35nQQXHMbLV7PMYQrYkj-0LAAI1HwACWdhxUCs3-Cy46P18PQQ" 
router = Router()
log = logging.getLogger(__name__)
# yt-dlp ищет в отдельном потоке, пока aiogram продолжает обрабатывать запросы.
search_workers = ThreadPoolExecutor(max_workers=6, thread_name_prefix="music-search")
SEARCH_TIMEOUT = 7
EXTERNAL_LIMIT = 12


def invalid_audio(error):
    message = str(error).upper()
    return any(code in message for code in (
        "AUDIO_CONTENT_TYPE_INVALID", "FILE_ID_INVALID", "WRONG_FILE_IDENTIFIER",
        "WRONG REMOTE FILE IDENTIFIER", "FILE_REFERENCE_EXPIRED",
        "INVALID FILE ID", "FILE_ID_EMPTY",
    ))


async def answer_results(q, rows, external):
    # Успешный ответ завершает inline-запрос. После ошибки ищем первую
    # пригодную группу и помечаем только подтверждённые одиночные ошибки.
    pending = [rows] if rows else []
    for _ in range(8):
        if not pending:
            break
        group = pending.pop()
        try:
            cached = [
                InlineQueryResultCachedAudio(id=str(row[0]), audio_file_id=row[1])
                for row in group
            ]
            await q.answer(cached + external, cache_time=30, is_personal=False)
            return
        except TelegramBadRequest as error:
            if not invalid_audio(error):
                raise
            if len(group) == 1:
                # Проверяем file_id без внешних результатов, прежде чем исключить его.
                if external:
                    try:
                        await q.answer(cached, cache_time=0)
                        log.info("Telegram отклонил смешанную выдачу, но принял сохранённое аудио: %s", error)
                        return
                    except TelegramBadRequest as cached_error:
                        if not invalid_audio(cached_error):
                            raise
                track_id, file_id, *_ = group[0]
                db.mark_unavailable(track_id, file_id)
                log.warning("Telegram отклонил аудио для записи %s", track_id)
            else:
                middle = len(group) // 2
                pending.extend((group[middle:], group[:middle]))
    await q.answer(external, cache_time=30 if external else 0)


async def search_source(source, query):
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(search_workers, downloader.search, source, query), SEARCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.info("Внешний поиск %s: таймаут %s с", source, SEARCH_TIMEOUT)
    except Exception as error:
        log.info("Внешний поиск %s: %s", source, error)
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
    text = (
f"<b>Привет! <tg-emoji emoji-id='{emoji_hello}' >✋</tg-emoji> Добро пожаловать в музыкального бота.</b>\n\n"

f"Что я умею:\n"
f"<b><tg-emoji emoji-id='{emoji_pods}' >🎧</tg-emoji> Напиши в любом чате @{me.username} и название трека</b>\n"
f"<b><tg-emoji emoji-id='{emoji_info}' >ℹ️</tg-emoji> /help — список команд</b>\n"

f"<b>Просто напиши название песни — и я начну!<tg-emoji emoji-id='{emoji_rocket}' >🚀</tg-emoji></b>")
    await message.answer(text, parse_mode="HTML" , disable_web_page_preview = True )

@router.message(Command("owner"))
async def cmd_owner(message : Message):
    await message.bot.send_chat_action(
            chat_id=message.chat.id, 
            action=ChatAction.TYPING
        )
    await asyncio.sleep(0.3)
    text = (
        f"<b><tg-emoji emoji-id='{emoji_diamond}' >💎</tg-emoji> Информация о проекте.</b>\n\n"
        f"<blockquote><b><tg-emoji emoji-id='{emoji_dev}' >🧑‍💻</tg-emoji> Разработчик:</b> @kiloware\n"
        f"<b><tg-emoji emoji-id='{emoji_message}' >✉️</tg-emoji> Связь:</b> <a href='https://t.me/kiloware'>Написать в ЛС.</a></blockquote>"
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
    text = (
f"Список команд:\n"
f"<b><tg-emoji emoji-id='{emoji_music}' >🎧</tg-emoji> @{me.username} название — поиск трека в любом чате</b>\n"
f"<b><tg-emoji emoji-id='{emoji_user}' >🧑‍💻</tg-emoji> /owner — узнать владельца бота</b>")

    await message.answer(text, parse_mode = "HTML")

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

    rows = db.search(query, 50)
    if not AUDIO_BASE_URL:
        log.info("Внешний поиск выключен: AUDIO_BASE_URL пуст")
        return await answer_results(q, rows, [])

    # Даже при совпадениях в SQLite ищем новые треки в обоих источниках.
    batches = await asyncio.gather(
        search_source("soundcloud", query), search_source("youtube", query),
    )
    cached_norms = {db.prepare(row[2], row[3])[2] for row in rows}
    tracks = {}
    for batch in batches:
        for track in batch:
            norm = db.prepare(track["title"], track["performer"])[2]
            if norm and norm not in cached_norms:
                tracks.setdefault(track["uid"], track)
    # HTTP-сервис находит источник по UID даже после перезапуска.
    db.save_candidates(list(tracks.values()))
    if len(tracks) < EXTERNAL_LIMIT:
        for track in db.search_candidates(query, EXTERNAL_LIMIT * 2):
            norm = db.prepare(track["title"], track["performer"])[2]
            if norm and norm not in cached_norms:
                tracks.setdefault(track["uid"], track)
            if len(tracks) >= EXTERNAL_LIMIT:
                break

    external = [search_result(track) for track in list(tracks.values())[:EXTERNAL_LIMIT]]
    log.info(
        "Inline-поиск: SQLite=%d, SoundCloud=%d, YouTube=%d, внешних в выдаче=%d",
        len(rows), len(batches[0]), len(batches[1]), len(external),
    )
    await answer_results(q, rows[:50 - len(external)], external)


@router.channel_post(F.audio, F.chat.id == CHANNEL_ID)
async def new_channel_track(m: Message):
    a = m.audio
    if db.add(a.file_unique_id, a.file_id, m.message_id, a.title, a.performer):
        db.commit()
    
@router.message(F.text & ~F.text.startswith('/'))
async def handle_message_search(m: Message):
    me = await m.bot.me()
    await m.answer(f"Поиск работает только через инлайн : \n\n @{me.username} название трека")
