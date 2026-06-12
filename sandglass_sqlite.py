"""
NexSandglass SQLite FTS5 加速层
================================
V1.4.4：sandglass.txt不动，SQLite分词FTS5平行加速。
纯 stdlib，零依赖。FTS5挂了自动降级。
"""

import os, re, sqlite3, threading

from sandglass_paths import _NB
_DB = os.path.join(_NB, "sandglass.db")
_lock = threading.Lock()
_last_sync_mtime = 0  # 记录上次同步时的 sandglass.txt 修改时间


def _tokenize(text: str) -> str:
    """FTS5专用分词：英文全词 + 中文2-gram。不用滑动窗口（滑动窗口用于mmap OR匹配）。"""
    import re as _re
    tokens = set()
    t = text.lower()
    # 英文全词（2+字母的数字词）
    tokens.update(_re.findall(r"[a-zA-Z0-9_]{2,}", t))
    # 中文2字词
    chars = "".join(_re.findall(r"[\u4e00-\u9fff]", text))
    for i in range(len(chars) - 1):
        tokens.add(chars[i : i + 2])
    return " ".join(sorted(t for t in tokens if t))


def _get_db():
    os.makedirs(os.path.dirname(_DB), exist_ok=True)
    conn = sqlite3.connect(_DB)
    conn.execute("PRAGMA journal_mode=WAL")  # 支持多进程并发
    conn.execute("PRAGMA synchronous=NORMAL")  # 性能优化，安全够用
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
                            rows.append((n, ts, sender, text))
                            fts.append((n, _tokenize(text)))
            conn.executemany("INSERT INTO sandglass VALUES(?,?,?,?)", rows)
            conn.executemany("INSERT INTO sandglass_fts(rowid, tokens) VALUES(?,?)", fts)
            conn.commit()
            return len(rows)
    except Exception:
        return -1


def sync_incremental() -> int:
    """增量同步。文件没变则跳过。返回新增条数。"""
    global _last_sync_mtime
    try:
        from sandglass_vault import _SANDGLASS, _parse_line
        # mtime检查——文件没变就跳过
        if os.path.exists(_SANDGLASS):
            mtime = os.path.getmtime(_SANDGLASS)
            if mtime == _last_sync_mtime and _last_sync_mtime > 0:
                return 0
            _last_sync_mtime = mtime
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
                            rows.append((n, ts, sender, text))
                            fts.append((n, _tokenize(text)))
                            added += 1
            if rows:
                conn.executemany("INSERT INTO sandglass VALUES(?,?,?,?)", rows)
                conn.executemany("INSERT INTO sandglass_fts(rowid, tokens) VALUES(?,?)", fts)
                conn.commit()
            return added
    except Exception:
        return 0


def search_in(line_ids: list, query: str, limit: int = 100) -> list:
    """FTS5 在指定行号列表中搜索排序。用于 mmap 初筛后的精排。"""
    try:
        tokens = _tokenize(query)
        if not tokens.strip() or not line_ids:
            return []
        ids_str = ",".join(str(int(i)) for i in line_ids)
        with _lock:
            conn = _get_db()
            sql = f"SELECT s.id, s.ts, s.text FROM sandglass_fts f JOIN sandglass s ON s.id=f.rowid WHERE s.id IN ({ids_str}) AND sandglass_fts MATCH ? ORDER BY rank"
            cur = conn.execute(sql, (tokens,))
            return [(row[0], row[1], row[2]) for row in cur.fetchall()]
    except Exception:
        return []


def search_year(query: str, year: str, limit: int = -1) -> list:
    """FTS5 按年份搜索。year='2026' 只搜该年。"""
    try:
        tokens = _tokenize(query)
        if not tokens.strip():
            return []
        with _lock:
            conn = _get_db()
            sql = "SELECT s.id, s.ts, s.text FROM sandglass_fts f JOIN sandglass s ON s.id=f.rowid WHERE s.ts LIKE ? AND sandglass_fts MATCH ? ORDER BY rank"
            if limit > 0:
                sql += f" LIMIT {limit}"
            cur = conn.execute(sql, (f"{year}%", tokens))
            return [(row[0], row[1], row[2]) for row in cur.fetchall()]
    except Exception:
        return []


def search(query: str, limit: int = 10) -> list:
    """FTS5搜索。limit=-1 全量。返回[(行号,时间,明文),...]。
    中文用AND语义，英文自动切换OR避免n-gram碎片化。"""
    try:
        tokens = _tokenize(query)
        if not tokens.strip():
            return []
        # 英文查询：OR语义（n-gram太多AND匹配不到）
        if any(c.isascii() and c.isalpha() for c in query):
            tokens = " OR ".join(tokens.split())
        with _lock:
            conn = _get_db()
            sql = "SELECT s.id, s.ts, s.text FROM sandglass_fts f JOIN sandglass s ON s.id = f.rowid WHERE sandglass_fts MATCH ? ORDER BY rank"
            if limit > 0:
                sql += f" LIMIT {limit}"
            cur = conn.execute(sql, (tokens,))
            return [(row[0], row[1], row[2]) for row in cur.fetchall()]
    except Exception:
        return []


def count() -> int:
    try:
        with _lock:
            return _get_db().execute("SELECT COUNT(*) FROM sandglass").fetchone()[0]
    except Exception:
        return 0
