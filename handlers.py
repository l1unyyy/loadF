from aiogram.types import (Message , InlineQueryResultCachedAudio, InlineQuery, InlineKeyboardButton,
                            InlineKeyboardMarkup, CallbackQuery, FSInputFile)
from aiogram import Router , F
from aiogram.filters import Command, CommandStart
import asyncio
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ChatAction
import logging
import downloader
import tracks_db as db
from config import ADMIN_ID, CHANNEL_ID


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


@router.inline_query()
async def inline_search(q: InlineQuery):
    if not q.query.strip():
        return await q.answer([])
        
    rows = db.search(q.query, 50)
    results = [InlineQueryResultCachedAudio(id=str(r[0]), audio_file_id=r[1]) for r in rows]
    
    try:
        await q.answer(results, cache_time=30, is_personal=False)
    except TelegramBadRequest as e:
        if "AUDIO_CONTENT_TYPE_INVALID" in str(e):
            log.warning(f"Битый file_id в поиске по запросу: {q.query}, ids {[r[0] for r in rows]}")
            await q.answer([], cache_time=30)
        else:
            raise 

@router.channel_post(F.audio, F.chat.id == CHANNEL_ID)
async def new_channel_track(m: Message):
    a = m.audio
    if db.add(a.file_unique_id, a.file_id, m.message_id, a.title, a.performer):
        db.commit()
    
@router.message(F.text & ~F.text.startswith('/'))
async def handle_message_search(m: Message):
    me = await m.bot.me()
    await m.answer(f"Поиск работает только через инлайн : \n @{me.username} название трека")
