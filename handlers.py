from aiogram.types import Message , InlineQueryResultCachedAudio, InlineQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram import Router , F
from aiogram.filters import Command, CommandStart
import asyncio
from aiogram.enums import ChatAction
import logging
import downloader
import tracks_db as db
from config import ADMIN_ID


router = Router()
log = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message : Message):
    log.info(f" Пользователь {message.from_user.id} (@{message.from_user.username}) запустил бота")
    await message.bot.send_chat_action(
        chat_id=message.chat.id, 
        action=ChatAction.TYPING
    )
    await asyncio.sleep(0.3)
    me = await message.bot.me()
    await message.answer(f""" Привет! 👋 Добро пожаловать в музыкального бота.
Что я умею:
🎵 Напиши в любом чате @{me.username} и название трека
💬 Или просто напиши название сюда
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
        "<blockquote>👤 <b>Разработчик:</b> @kiloware\n"
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

found = {}                      
locks = {}                      
sem = asyncio.Semaphore(3)      


def label(e):
    name = f'{e["performer"]} — {e["title"]}' if e["performer"] else e["title"]
    return ("⚡ " if e["cached"] else "") + name[:58]

@router.inline_query()
async def inline_search(q: InlineQuery):
    rows = db.search(q.query, 50) if q.query.strip() else []
    results = [InlineQueryResultCachedAudio(id=str(r[0]), audio_file_id=r[1]) for r in rows]
    await q.answer(results, cache_time=30, is_personal=False)

async def run_search(m: Message, query: str):
    query = query.strip()
    if not query:
        return await m.answer("Напиши название трека или исполнителя 🎵")
    wait = await m.answer("🔎 В поиске....")
    local = db.search(query, 5)
    try:
        remote = await asyncio.to_thread(downloader.sc_search, query)
        
    except Exception:
        log.exception("soundcloud search failed q=%r", query)
        remote = []

    entries, seen = [], set()
    for r in local:
        entries.append(dict(kind="db", id=r[0], title=r[2], performer=r[3], cached=True))
        seen.add(r[0])
    for t in remote:
        
        row = db.find(t["uid"], t["title"], t["performer"])
        if row:                                   # этот трек уже есть в базе
            if row[0] not in seen:
                seen.add(row[0])
                entries.append(dict(kind="db", id=row[0], title=t["title"],
                                    performer=t["performer"], cached=True))
        else:
            entries.append(dict(kind="sc", cached=False, **t))
    entries = entries[:15]
    log.info("search q=%r db=%d sc=%d shown=%d", query, len(local), len(remote), len(entries))

    await wait.delete()
    if not entries:
        return await m.answer("Ничего не нашёл 😕. Попробуй написать иначе.")
    found[m.from_user.id] = entries
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label(e), callback_data=f"p:{i}")]
        for i, e in enumerate(entries)])
    await m.answer("Выбери трек (⚡Придёт мгновенно):", reply_markup=kb)

@router.message(F.text & ~F.text.startswith('/'))
async def handle_message_search(m: Message):
    await run_search(m, m.text)