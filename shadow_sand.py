"""
NexSandglass — 影子沙 (Shadow Sand)
=====================================
轻量SQLite投影层。不碰沙子原文，只存索引元数据。
投石问路之前先查影子沙——脱口而出级速度。
零依赖：sqlite3是Python stdlib。
"""
import sqlite3, os, re
from collections import defaultdict

from sandglass_paths import _NB

_SHADOW_DB = os.path.join(_NB, "shadow_sand.db")


def set_shadow_path(path: str):
    """重定向影子沙路径——基准测试用。"""
    global _SHADOW_DB, _conn
    _SHADOW_DB = path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trust (
    line_num    INTEGER PRIMARY KEY,  -- 对应sandglass.txt行号
    score       REAL DEFAULT 0.5,     -- 信任分 [0,1]
    helpful     INTEGER DEFAULT 0,    -- 好评次数
    unhelpful   INTEGER DEFAULT 0,    -- 差评次数
    retrievals  INTEGER DEFAULT 0,    -- 被检索次数
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS entities (
    name        TEXT NOT NULL,
    line_nums   TEXT DEFAULT '',      -- 逗号分隔的行号列表
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);

CREATE TABLE IF NOT EXISTS fact_tags (
    line_num    INTEGER PRIMARY KEY,
    category    TEXT DEFAULT 'general',
    tags        TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now'))
);
"""

_ENTITY_RE = re.compile(
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b|'   # 英文大写多词
    r'"([^"]+)"|'                                   # 双引号
    r"'([^']+)'|"                                   # 单引号
    r'([\u4e00-\u9fff]{2,4})'                     # 中文2-4字（人名/术语）
)

_conn = None
def shadow_mbti() -> str:
    """读取最近记录的MBTI类型。影子沙——会变，不属于画像。"""
    try:
        db = _get_conn()
        db.execute("CREATE TABLE IF NOT EXISTS mbti (mbti TEXT, ts TEXT DEFAULT (datetime('now')))")
        row = db.execute("SELECT mbti FROM mbti ORDER BY ts DESC LIMIT 1").fetchone()
        return row[0] if row else ""
    except: return ""

def shadow_mbti_set(mbti: str) -> None:
    """记录MBTI变更。"""
    db = _get_conn()
    db.execute("CREATE TABLE IF NOT EXISTS mbti (mbti TEXT, ts TEXT DEFAULT (datetime('now')))")
    db.execute("INSERT INTO mbti (mbti) VALUES (?)", (mbti.upper(),))
    db.commit()



_commit_pending = 0

def _get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_SHADOW_DB, check_same_thread=False)
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn

def _maybe_commit():
    global _commit_pending
    _commit_pending += 1
    if _commit_pending >= 3:
        _get_conn().commit()
        _commit_pending = 0


# ═══════════════════ 查询（脱口而出层） ═══════════════════

def shadow_search(query: str, limit: int = 10) -> list:
    """影子沙优先搜索。返回 [(行号, 信任分), ...]"""
    db = _get_conn()
    words = [w for w in re.findall(r'\w+', query.lower()) if len(w) > 1]
    # 方法1: 实体名匹配（最快）
    results = []
    for w in words:
        rows = db.execute(
            "SELECT line_nums FROM entities WHERE name LIKE ? LIMIT 1",
            (f"%{w}%",)
        ).fetchall()
        for row in rows:
            for ln in row[0].split(","):
                if ln.strip().isdigit():
                    results.append(int(ln.strip()))

    # 方法2: 标签匹配
    tag_rows = db.execute(
        "SELECT line_num FROM fact_tags WHERE tags LIKE ? OR category LIKE ? LIMIT ?",
        (f"%{query}%", f"%{query}%", limit)
    ).fetchall()
    for row in tag_rows:
        results.append(row[0])

    # 去重 + 信任加权排序
    if results:
        unique = list(set(results))
        scored = []
        for ln in unique[:limit * 3]:
            tr = db.execute(
                "SELECT score FROM trust WHERE line_num = ?", (ln,)
            ).fetchone()
            score = tr[0] if tr else 0.5
            scored.append((score, ln))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:limit]

    return []


def shadow_boost(candidate_lines: set, limit: int = 10) -> list:
    """对投石问路的候选行号做影子加权排序。
    返回 [(行号, 信任分), ...]"""
    if not candidate_lines:
        return []
    db = _get_conn()
    placeholders = ",".join("?" * len(candidate_lines))
    rows = db.execute(
        f"SELECT line_num, score FROM trust WHERE line_num IN ({placeholders})",
        list(candidate_lines)
    ).fetchall()
    trust_map = {r[0]: r[1] for r in rows}
    scored = [(trust_map.get(ln, 0.5), ln) for ln in candidate_lines]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


# ═══════════════════ 写入（落沙后同步） ═══════════════════

def shadow_index(text: str, category: str = "general", tags: str = "", line_num: int = 0) -> None:
    try:
        from sandglass_think import scene_mode
        if scene_mode() == 'exam': category = 'exam_' + category
    except: pass
    """落沙后同步——调用方传入实际行号，避免COUNT(*)偏移。"""
    db = _get_conn()
    # 行号由调用方传入（sandglass_log 写入后传实际行号）
    if line_num <= 0:
        line_num = db.execute("SELECT COUNT(*) FROM trust").fetchone()[0] + 1

    # 提取实体
    for m in _ENTITY_RE.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3) or ""
        name = name.strip()
        if name and len(name) > 1:
            row = db.execute(
                "SELECT line_nums FROM entities WHERE name = ?", (name,)
            ).fetchone()
            if row:
                nums = set(row[0].split(",")) | {str(line_num)}
                db.execute(
                    "UPDATE entities SET line_nums = ? WHERE name = ?",
                    (",".join(sorted(nums, key=int)), name)
                )
            else:
                db.execute(
                    "INSERT INTO entities (name, line_nums) VALUES (?, ?)",
                    (name, str(line_num))
                )

    # 写入信任记录
    db.execute(
        "INSERT OR IGNORE INTO trust (line_num, score) VALUES (?, 0.5)",
        (line_num,)
    )

    # 写入标签
    if category != "general" or tags:
        db.execute(
            "INSERT OR REPLACE INTO fact_tags (line_num, category, tags) VALUES (?, ?, ?)",
            (line_num, category, tags)
        )

    _maybe_commit()


# ═══════════════════ 反馈 ═══════════════════

def shadow_feedback(line_num: int, helpful: bool) -> dict:
    """信任评分反馈。"""
    db = _get_conn()
    row = db.execute(
        "SELECT score, helpful, unhelpful FROM trust WHERE line_num = ?",
        (line_num,)
    ).fetchone()
    if not row:
        db.execute("INSERT INTO trust (line_num, score) VALUES (?, 0.5)", (line_num,))
        old_score = 0.5
    else:
        old_score = row[0]

    delta = 0.05 if helpful else -0.10
    new_score = max(0.0, min(1.0, old_score + delta))
    col = "helpful" if helpful else "unhelpful"

    db.execute(
        f"UPDATE trust SET score = ?, {col} = {col} + 1, updated_at = datetime('now') WHERE line_num = ?",
        (new_score, line_num)
    )
    _maybe_commit()
    return {"line_num": line_num, "old_trust": old_score, "new_trust": new_score}


def shadow_retrieval_bump(line_nums: list) -> None:
    """标记检索——增加retrievals计数。"""
    if not line_nums:
        return
    db = _get_conn()
    placeholders = ",".join("?" * len(line_nums))
    db.execute(
        f"UPDATE trust SET retrievals = retrievals + 1 WHERE line_num IN ({placeholders})",
        line_nums
    )
    _maybe_commit()
