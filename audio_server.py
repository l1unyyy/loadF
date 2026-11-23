import asyncio
import logging
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic

from aiohttp import web
from aiogram.types import FSInputFile

import downloader
import tracks_db as db
from config import AUDIO_BASE_URL, AUDIO_PORT, CHANNEL_ID

log = logging.getLogger(__name__)
FILE_TTL = 180
MAX_PENDING = 4


class AudioServer:
    def __init__(self, bot):
        self.bot = bot
        self.pending = {}
        self.files = {}
        self.uploads = {}
        # Один yt-dlp/FFmpeg за раз для VPS с 1 ГБ RAM.
        self.download_slot = asyncio.Semaphore(1)

    async def prepare(self, uid, candidate):
        title, performer, url, source = candidate
        queued_at = monotonic()
        async with self.download_slot:
            started_at = monotonic()
            filename, directory = await asyncio.to_thread(downloader.download, url)
        ready_at = monotonic()
        log.info("MP3 %s готов: очередь %.2f с, скачивание и подготовка %.2f с",
                 uid, started_at - queued_at, ready_at - started_at)
        path = Path(filename)
        self.files[uid] = (path, directory, ready_at + FILE_TTL)
        if not db.find(uid, title, performer):
            # Отдача MP3 может начаться, пока отдельная задача загружает его в канал.
            self.uploads[uid] = asyncio.create_task(self.publish(uid, path, candidate))
        return path

    async def publish(self, uid, path, candidate):
        title, performer, _, source = candidate
        started_at = monotonic()
        try:
            message = await self.bot.send_audio(
                CHANNEL_ID, FSInputFile(path), title=title[:64], performer=performer[:64] or None,
            )
            uploaded_at = monotonic()
            db.add(uid, message.audio.file_id, message.message_id, title, performer, source)
            db.commit()
            log.info("Трек %s опубликован: Telegram %.2f с, запись в SQLite %.3f с",
                     uid, uploaded_at - started_at, monotonic() - uploaded_at)
        except Exception:
            log.exception("Не удалось сохранить трек %s в канале", uid)
        finally:
            self.uploads.pop(uid, None)

    async def prepare_track(self, uid, candidate):
        try:
            return await self.prepare(uid, candidate)
        except Exception:
            log.exception("Не удалось подготовить трек %s", uid)
            return None
        finally:
            self.pending.pop(uid, None)

    async def audio(self, request):
        uid = request.match_info["uid"]
        candidate = db.get_candidate(uid)
        if candidate is None:
            raise web.HTTPNotFound()

        cached = self.files.get(uid)
        if cached:
            path, directory, _ = cached
            self.files[uid] = (path, directory, monotonic() + FILE_TTL)
        else:
            task = self.pending.get(uid)
            if task is None:
                if len(self.pending) + len(self.uploads) >= MAX_PENDING:
                    raise web.HTTPServiceUnavailable(headers={"Retry-After": "5"})
                task = asyncio.create_task(self.prepare_track(uid, candidate))
                self.pending[uid] = task
            # Повторные HEAD/GET используют одну подготовку, даже если клиент отключился.
            path = await asyncio.shield(task)
            if path is None:
                raise web.HTTPBadGateway()

        return web.FileResponse(path, headers={"Content-Type": "audio/mpeg"})

    async def cleanup(self):
        while True:
            await asyncio.sleep(30)
            now = monotonic()
            for uid, (_, directory, expiry) in list(self.files.items()):
                if expiry <= now and uid not in self.uploads:
                    self.files.pop(uid)
                    shutil.rmtree(directory, ignore_errors=True)

    async def close(self):
        await asyncio.gather(*self.pending.values(), return_exceptions=True)
        await asyncio.gather(*self.uploads.values(), return_exceptions=True)
        for _, directory, _ in self.files.values():
            shutil.rmtree(directory, ignore_errors=True)


@asynccontextmanager
async def serve_audio(bot):
    if not AUDIO_BASE_URL:
        yield
        return

    service = AudioServer(bot)
    app = web.Application()
    app.router.add_get("/tracks/{uid}.mp3", service.audio)
    runner = web.AppRunner(app)
    await runner.setup()
    cleanup = asyncio.create_task(service.cleanup())
    try:
        await web.TCPSite(runner, "127.0.0.1", AUDIO_PORT).start()
        yield
    finally:
        await runner.cleanup()
        cleanup.cancel()
        await asyncio.gather(cleanup, return_exceptions=True)
        await service.close()
