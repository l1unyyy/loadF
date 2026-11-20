from aiogram.types import Message
from aiogram import Router
from aiogram.filters import Command, CommandStart
import asyncio


router = Router()

@router.message(CommandStart())
async def cmd_start(message : Message):
    await message.answer("Для того, что бы найти трек напиши \n\n" \
    "@loadfbot название трека")
