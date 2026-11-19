from aiogram.exceptions import (TelegramBadRequest, TelegramForbiddenError,
                                TelegramNetworkError, TelegramRetryAfter,
                                TelegramServerError)
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram import Bot
from config import TG_TOKEN, CHANNEL_ID, ADMIN_ID
import tracks_db as db
import asyncio
import os
import sys

POS_FILE = "import_pos.txt"
