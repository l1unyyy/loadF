"""Пополняет Telegram-канал и SQLite треками из SoundCloud."""

import argparse
import asyncio
import logging
import re
import shutil

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import FSInputFile
from yt_dlp.utils import DownloadError

import downloader


log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artists", nargs="+", metavar="ИСПОЛНИТЕЛЬ")
    parser.add_argument("--limit", type=int, default=5, help="Новых треков на исполнителя")
    parser.add_argument("--dry-run", action="store_true", help="Показать список без публикации")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit должен быть положительным")
    if any(not any(char.isalnum() for char in artist) for artist in args.artists):
        parser.error("Укажи имя исполнителя для каждого запроса")
    return args


def words(value):
    return re.findall(r"[^\W_]+", value.casefold())


async def publish(bot, channel_id, path, title, performer):
    for attempt in range(2):
        try:
            return await bot.send_audio(
                channel_id, FSInputFile(path), title=title[:64], performer=performer[:64],
            )
        except TelegramRetryAfter as error:
            if attempt:
                raise
            log.info("Лимит Telegram. Повтор через %s с", error.retry_after)
            await asyncio.sleep(error.retry_after + 1)


async def seed(artists, limit, db, channel_id, bot=None):
    total = 0
    seen = set()
    for artist in artists:
        log.info("Поиск в SoundCloud: %s", artist)
        try:
            tracks = await asyncio.to_thread(downloader.search, "soundcloud", artist, limit * 4)
        except DownloadError as error:
            log.error("Поиск «%s» завершился ошибкой: %s", artist, error)
            continue

        artist_words = " ".join(words(artist))
        added = 0
        for track in tracks:
            uid, title, performer = track["uid"], track["title"], track["performer"]
            title, performer, norm = db.prepare(title, performer)
            # Поиск SoundCloud возвращает и похожих артистов. Сверяем имя целиком по словам.
            if not norm or f" {artist_words} " not in f" {' '.join(words(performer))} ":
                continue
            if norm in seen or db.find(uid, title, performer):
                continue

            if bot is None:
                log.info("Будет добавлен: %s — %s", performer, title)
            else:
                try:
                    path, folder = await asyncio.to_thread(downloader.download, track["url"])
                except (DownloadError, OSError, RuntimeError) as error:
                    log.warning("Пропускаю «%s»: %s", title, error)
                    continue
                try:
                    # Пока файл скачивался, его мог сохранить запущенный бот.
                    if db.find(uid, title, performer):
                        continue
                    message = await publish(bot, channel_id, path, title, performer)
                    with db.con:
                        stored = db.add(uid, message.audio.file_id, message.message_id,
                                        title, performer, track["source"])
                    if not stored:
                        continue
                    log.info("Добавлен: %s — %s", performer, title)
                finally:
                    shutil.rmtree(folder, ignore_errors=True)

            seen.add(norm)
            added += 1
            if added == limit:
                break

        log.info("%s: %s %d из %d", artist, "найдено" if bot is None else "добавлено", added, limit)
        total += added
    return total


async def main(args):
    import tracks_db as db

    if args.dry_run:
        return await seed(args.artists, args.limit, db, None)

    from config import CHANNEL_ID, TG_TOKEN

    async with Bot(TG_TOKEN) as bot:
        return await seed(args.artists, args.limit, db, CHANNEL_ID, bot)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    total = asyncio.run(main(args))
    log.info("Итого %s: %d", "найдено" if args.dry_run else "добавлено", total)
