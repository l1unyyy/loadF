import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracks.db")

con = sqlite3.connect(DB_PATH, check_same_thread=False)
con.execute("PRAGMA journal_mode=WAL")
con.executescript("""
CREATE TABLE IF NOT EXISTS tracks(
    id        INTEGER PRIMARY KEY,
    uid       TEXT UNIQUE,      -- file_unique_id: один и тот же файл не добавится дважды
    norm      TEXT UNIQUE,      -- «исполнительназвание» без символов: убирает дубли
    file_id   TEXT NOT NULL,
    msg_id    INTEGER,          -- пост в канале (запасной вариант)
    title     TEXT,
    performer TEXT,
    source    TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    title, performer,
    content='tracks', content_rowid='id',
    tokenize='unicode61', prefix='2 3'
);
DROP TRIGGER IF EXISTS tracks_ai;
DROP TRIGGER IF EXISTS tracks_ad;
DROP TRIGGER IF EXISTS tracks_au;
""")

TLD = r"(?:net|ru|com|org|me|su|ua|fm|cc|info|biz)"
JUNK = [
    re.compile(rf"\s*[\[(][^\])]*\.{TLD}[^\])]*[\])]", re.I),   # [mp3hap.net]
    re.compile(rf"\s*\b[\w-]+\.{TLD}\s*$", re.I),                # muzofond.com в конце
    re.compile(r"\s*[\[(]\s*без рекламы\s*[\])]", re.I),         # (без рекламы)
    re.compile(r"<unknown>", re.I),
]


def clean(s):
    s = s or ""
    for p in JUNK:
        s = p.sub("", s)
    return re.sub(r"\s+", " ", s).strip(" -–—_")


def prepare(title, performer):
    title, performer = clean(title), clean(performer)
    if not performer and " - " in title:
        performer, title = [x.strip() for x in title.split(" - ", 1)]
    norm = re.sub(r"[\W_]+", "", f"{performer}{title}".lower())
    return title, performer, norm


def add(uid, file_id, msg_id, title, performer, source="telegram_channel"):
    """True, если трек новый. Дубли и пустые названия пропускаются."""
    title, performer, norm = prepare(title, performer)
    if not norm:
        return False
    cur = con.execute(
        "INSERT OR IGNORE INTO tracks(uid,norm,file_id,msg_id,title,performer,source)"
        " VALUES(?,?,?,?,?,?,?)",
        (uid, norm, file_id, msg_id, title, performer, source))
    if cur.rowcount != 1:
        return False
    con.execute("INSERT INTO tracks_fts(rowid, title, performer) VALUES (?,?,?)",
                (cur.lastrowid, title, performer))
    return True


def find(uid, title, performer):
    """Есть ли такой трек в базе (по id источника ИЛИ по «исполнитель+название»)."""
    _, _, norm = prepare(title, performer)
    return con.execute("SELECT id, file_id, msg_id FROM tracks WHERE uid=? OR norm=?",
                       (uid, norm)).fetchone()


def count():
    return con.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]


def search(q, limit=30):
    """Сначала быстрый FTS5-поиск по началу слов; если пусто, поиск по подстроке."""
    toks = re.findall(r"\w+", q.lower())
    if not toks:
        return []
    fts = " ".join(f'"{t}"*' for t in toks)
    rows = con.execute(
        "SELECT t.id, t.file_id, t.title, t.performer FROM tracks_fts "
        "JOIN tracks t ON t.id = tracks_fts.rowid "
        "WHERE tracks_fts MATCH ? ORDER BY bm25(tracks_fts) LIMIT ?",
        (fts, limit)).fetchall()
    if rows:
        return rows
    where = " AND ".join("norm LIKE ?" for _ in toks)
    return con.execute(
        f"SELECT id, file_id, title, performer FROM tracks WHERE {where} LIMIT ?",
        [f"%{t}%" for t in toks] + [limit]).fetchall()


def get(track_id):
    return con.execute("SELECT file_id, msg_id FROM tracks WHERE id=?",
                       (track_id,)).fetchone()


def commit():
    con.commit()
