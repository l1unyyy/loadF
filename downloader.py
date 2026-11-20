import glob
import os
import shutil
import tempfile

import yt_dlp


def parse_results(entries):
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
        url = e.get("url") or e.get("webpage_url")
        if not (title and url and e.get("id")):
            continue
        out.append(dict(uid=f"sc{e['id']}", title=title, performer=performer, url=url))
    return out


def sc_search(q, n=20):
    """Список из n треков SoundCloud БЕЗ скачивания (около секунды)."""
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "socket_timeout": 15}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"scsearch{n}:{q}", download=False)
    return parse_results(info.get("entries"))


def download(url):
    tmp = tempfile.mkdtemp(prefix="muz_")
    try:
        opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 20,
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3", "preferredquality": "192"}],
        }
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([url])
        files = glob.glob(os.path.join(tmp, "*.mp3"))
        if not files:
            raise RuntimeError("mp3 не создан (проверь, что установлен ffmpeg)")
        return files[0], tmp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise