import glob
import os
import shutil
import tempfile

import yt_dlp


def parse_results(entries, source):
    """Приводит результаты обоих источников к одному формату для inline-выдачи."""
    out = []
    for e in entries or []:
        if not e:
            continue
        d = e.get("duration")
        if d and not (45 <= d <= 900):          # отсекаем обрезки и миксы
            continue
        title = (e.get("title") or "").strip()
        performer = (e.get("uploader") or "").strip()
        if " - " in title:                       # «Исполнитель - Название»
            performer, title = [x.strip() for x in title.split(" - ", 1)]
        track_id = e.get("id")
        if not (title and track_id):
            continue
        url = (f"https://www.youtube.com/watch?v={track_id}" if source == "youtube"
               else e.get("webpage_url") or e.get("url"))
        if not url or not url.startswith(("https://soundcloud.com/", "https://www.youtube.com/")):
            continue
        out.append(dict(uid=f"{source}:{track_id}", title=title, performer=performer,
                        url=url, source=source))
    return out

def search(source, q, n=6):
    """Ищет метаданные через yt-dlp. Аудио загружается отдельно по выбору пользователя."""
    prefix = {"soundcloud": "scsearch", "youtube": "ytsearch"}[source]
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
            "socket_timeout": 3, "extractor_retries": 0, "retries": 0}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"{prefix}{n}:{q}", download=False)
        return parse_results(info.get("entries"), source)
    
def download(url):
    tmp = tempfile.mkdtemp(prefix="muz_")
    try:
        opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 20,
            "format": "bestaudio/best",
            "retries": 2, "fragment_retries": 2,
            "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3", "preferredquality": "192"}],
        }
        if node := shutil.which("node"):
            opts["js_runtimes"] = {"node": {"path": node}}
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([url])
        files = glob.glob(os.path.join(tmp, "*.mp3"))
        if not files:
            raise RuntimeError("mp3 не создан (проверь, что установлен ffmpeg)")
        return files[0], tmp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
