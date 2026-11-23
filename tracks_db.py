import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracks.db")

con = sqlite3.connect(DB_PATH, check_same_thread=False)
con.execute("PRAGMA journal_mode=WAL")
con.executescript("""
CREATE TABLE IF NOT EXISTS tracks(
    id        INTEGER PRIMARY KEY,
    uid       TEXT UNIQUE,      
    norm      TEXT UNIQUE,      
    file_id   TEXT NOT NULL,
    msg_id    INTEGER,          
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
CREATE TABLE IF NOT EXISTS unavailable_audio(
    track_id INTEGER PRIMARY KEY,
    file_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inline_candidates(
    uid TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    performer TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL
);
""")

TLD = r"(?:net|ru|com|org|me|su|ua|fm|cc|info|biz)"
JUNK = [
    re.compile(rf"\s*[\[(][^\])]*\.{TLD}[^\])]*[\])]", re.I),   
    re.compile(rf"\s*\b[\w-]+\.{TLD}\s*$", re.I),                
    re.compile(r"\s*[\[(]\s*без рекламы\s*[\])]", re.I),         
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
    """Добавляет трек или обновляет отклонённый файл. Вызывающий код делает commit."""
    title, performer, norm = prepare(title, performer)
    if not norm:
        return False
    cur = con.execute(
        "INSERT OR IGNORE INTO tracks(uid,norm,file_id,msg_id,title,performer,source)"
        " VALUES(?,?,?,?,?,?,?)",
        (uid, norm, file_id, msg_id, title, performer, source))
    if cur.rowcount != 1:
        # При замене файла заголовок и rowid сохраняются, поэтому FTS обновлять не нужно.
        repaired = con.execute(
            "UPDATE tracks SET file_id=?, msg_id=?, source=? "
            "WHERE id=(SELECT t.id FROM tracks t JOIN unavailable_audio b "
            "ON b.track_id=t.id AND b.file_id=t.file_id "
            "WHERE (t.uid=? OR t.norm=?) AND t.file_id<>? ORDER BY t.uid=? DESC LIMIT 1)",
            (file_id, msg_id, source, uid, norm, file_id, uid),
        )
        return repaired.rowcount == 1
    con.execute("INSERT INTO tracks_fts(rowid, title, performer) VALUES (?,?,?)",
                (cur.lastrowid, title, performer))
    return True

def find(uid, title, performer):
    """Есть ли такой трек в базе (по id источника ИЛИ по «исполнитель+название»)."""
    _, _, norm = prepare(title, performer)
    return con.execute(
        f"SELECT t.id, t.file_id, t.msg_id FROM tracks t "
        f"WHERE (t.uid=? OR t.norm=?) AND {AVAILABLE} ORDER BY t.uid=? DESC LIMIT 1",
        (uid, norm, uid),
    ).fetchone()

AVAILABLE = ("NOT EXISTS (SELECT 1 FROM unavailable_audio b "
             "WHERE b.track_id=t.id AND b.file_id=t.file_id)")


def mark_unavailable(track_id, file_id):
    """Помечает конкретный file_id, если он по-прежнему привязан к записи."""
    with con:
        con.execute(
            "INSERT OR REPLACE INTO unavailable_audio(track_id, file_id) "
            "SELECT id, file_id FROM tracks WHERE id=? AND file_id=?",
            (track_id, file_id),
        )

def save_candidates(tracks):
    """Сохраняет ссылки источников отдельно от треков, уже загруженных в канал."""
    with con:
        con.executemany(
            "INSERT INTO inline_candidates(uid,title,performer,url,source) "
            "VALUES(:uid,:title,:performer,:url,:source) ON CONFLICT(uid) DO UPDATE SET "
            "title=excluded.title, performer=excluded.performer, url=excluded.url",
            tracks,
        )

def get_candidate(uid):
    return con.execute(
        "SELECT title, performer, url, source FROM inline_candidates WHERE uid=?",
        (uid,),
    ).fetchone()


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
        f"WHERE tracks_fts MATCH ? AND {AVAILABLE} ORDER BY bm25(tracks_fts) LIMIT ?",
        (fts, limit)).fetchall()
    if rows:
        return rows
    where = " AND ".join("norm LIKE ?" for _ in toks)
    return con.execute(
        f"SELECT id, file_id, title, performer FROM tracks t WHERE {where} AND {AVAILABLE} LIMIT ?",
        [f"%{t}%" for t in toks] + [limit]).fetchall()



def get(track_id):
    return con.execute("SELECT file_id, msg_id FROM tracks WHERE id=?",
                       (track_id,)).fetchone()


def commit():
    con.commit()
