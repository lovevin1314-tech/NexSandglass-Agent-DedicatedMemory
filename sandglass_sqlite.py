"""
NexSandglass SQLite FTS5 加速层
================================
V1.4.4：sandglass.txt不动，SQLite分词FTS5平行加速。
纯 stdlib，零依赖。FTS5挂了自动降级。
"""

import os, re, sqlite3, threading

_DB = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.db")
_lock = threading.Lock()


def _tokenize(text: str) -> str:
    """2-gram分词，空格分隔。和vault._tokenize一致。"""
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    tokens = [chars[i:i+2] for i in range(len(chars)-1)]
    tokens.extend(re.findall(r"[a-zA-Z0-9_]{2,}", text.lower()))
    return " ".join(tokens)


def _get_db():
    os.makedirs(os.path.dirname(_DB), exist_ok=True)
    conn = sqlite3.connect(_DB)
    conn.execute("CREATE TABLE IF NOT EXISTS sandglass (id INTEGER PRIMARY KEY, ts TEXT, sender TEXT, text TEXT)")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS sandglass_fts USING fts5(tokens)")
    conn.commit()
    return conn


def sync_all() -> int:
    """全量同步。返回条数，失败返回-1。"""
    try:
        from sandglass_vault import _SANDGLASS, _parse_line
        with _lock:
            conn = _get_db()
            conn.execute("DELETE FROM sandglass")
            conn.execute("DELETE FROM sandglass_fts")
            rows = []; fts = []
            if os.path.exists(_SANDGLASS):
                with open(_SANDGLASS, "r", encoding="utf-8") as f:
                    for n, line in enumerate(f, 1):
                        ts, sender, text = _parse_line(line)
                        if ts:
                            rows.append((n, ts, sender, text[:500]))
                            fts.append((n, _tokenize(text)))
            conn.executemany("INSERT INTO sandglass VALUES(?,?,?,?)", rows)
            conn.executemany("INSERT INTO sandglass_fts(rowid, tokens) VALUES(?,?)", fts)
            conn.commit()
            return len(rows)
    except Exception:
        return -1


def sync_incremental() -> int:
    """增量同步。返回新增条数。"""
    try:
        from sandglass_vault import _SANDGLASS, _parse_line
        with _lock:
            conn = _get_db()
            cur = conn.execute("SELECT MAX(id) FROM sandglass")
            max_id = cur.fetchone()[0] or 0
            rows = []; fts = []; added = 0
            if os.path.exists(_SANDGLASS):
                with open(_SANDGLASS, "r", encoding="utf-8") as f:
                    for n, line in enumerate(f, 1):
                        if n <= max_id: continue
                        ts, sender, text = _parse_line(line)
                        if ts:
                            rows.append((n, ts, sender, text[:500]))
                            fts.append((n, _tokenize(text)))
                            added += 1
            if rows:
                conn.executemany("INSERT INTO sandglass VALUES(?,?,?,?)", rows)
                conn.executemany("INSERT INTO sandglass_fts(rowid, tokens) VALUES(?,?)", fts)
                conn.commit()
            return added
    except Exception:
        return 0


def search(query: str, limit: int = 10) -> list:
    """FTS5搜索。返回[(行号,时间,明文),...]。失败返回[]。"""
    try:
        tokens = _tokenize(query)
        if not tokens.strip():
            return []
        with _lock:
            conn = _get_db()
            cur = conn.execute(
                "SELECT s.id, s.ts, s.text FROM sandglass_fts f "
                "JOIN sandglass s ON s.id = f.rowid "
                "WHERE sandglass_fts MATCH ? ORDER BY rank LIMIT ?",
                (tokens, limit)
            )
            return [(row[0], row[1], row[2][:200]) for row in cur.fetchall()]
    except Exception:
        return []


def count() -> int:
    try:
        with _lock:
            return _get_db().execute("SELECT COUNT(*) FROM sandglass").fetchone()[0]
    except Exception:
        return 0
