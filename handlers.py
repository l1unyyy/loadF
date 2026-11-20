from aiogram.types import Message
from aiogram import Router
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