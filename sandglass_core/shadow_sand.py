"""
NexSandglass — 影子沙 (Shadow Sand)
=====================================
轻量SQLite投影层。不碰沙子原文，只存索引元数据。
投石问路之前先查影子沙——脱口而出级速度。
零依赖：sqlite3是Python stdlib。
"""
import sqlite3, os, re, threading
from collections import defaultdict

from sandglass_paths import _NB
import logging
logger = logging.getLogger(__name__)

_SHADOW_DB = os.path.join(_NB, "shadow_sand.db")


def set_shadow_path(path: str):
    """重定向影子沙路径——基准测试用。"""
    global _SHADOW_DB, _conn, _conn_inode
    _SHADOW_DB = path
    # 路径变了必须废弃旧连接，否则仍指向旧库
    _close_conn()

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

CREATE TABLE IF NOT EXISTS fact_tags_archive (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT DEFAULT 'general',
    tags        TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now'))
);
"""

# 阶段B 残片闸前缀——口语代词/时间词开头的4字组多为长句切碎残片
_TAG_FRAGMENT_4_PREFIXES = (
    '你是', '你说', '今天', '昨天', '明天', '我在', '我刚', '你来', '你给',
    '你有', '你没', '你现在', '我今天', '你今天', '你怎么', '你什么', '我问',
    '我想', '你觉', '你能', '你要', '你的', '我的', '你们', '我们这个', '我应该',
)

_ENTITY_RE = re.compile(
    r'\b([A-Z][a-z]{1,}(?:\s+[A-Z][a-z]+)*)\b|'     # 英文单/多词(Caroline, New York)
    r'\b([A-Z]{2,})\b|'                                # 全大写(LGBTQ, API)
    r'"([^"]+)"|'                                       # 双引号
    r"'([^']+)'|"                                       # 单引号
    r'([\u4e00-\u9fff]{2,4})'                         # 中文2-4字
)

# ═══════════════════ V2.20.4 fact_tags 质量闸 ═══════════════════
# 背景：fact_tags 21,401 行是 6/17 单日 17,185 行写入的历史残留（旧全文regex提取），
# 行号 95.4% 越界；V2.20.2 修复后注入首次生效把垃圾顶进【你是谁】关注行。
# 以下 注入三道闸 + 行号门控 + 内容特征过滤 按 Hermes 八步分析判定实施（2026-08-13）。

# 中文停用词——复用 search_router.py ZH_STOP + scene_l3.py STOPWORDS 词表，
# 并补充对话高频虚词（好的/亲爱的/一下/问题/现在/对的/最近的对/我在/爱的/你/我/他 等）
_TAG_STOPWORDS = frozenset({
    # ── search_router.py ZH_STOP 词表（逐词复用）──
    '上次', '那个', '这个', '一下', '我想', '帮我', '多少钱', '怎么样', '怎么办',
    '有没有', '是不是', '能不能', '可不可以', '什么是', '什么叫', '怎么', '什么', '哪',
    '吗', '呢', '啊', '吧', '的', '了', '是', '在', '有', '我', '你', '他', '她', '它',
    '们', '这', '那', '很', '都', '也', '就', '还', '要', '会', '能', '可以', '应该',
    '把', '被', '让', '给', '对', '从', '到', '和', '与', '或', '但', '而', '所以',
    '因为', '如果', '虽然', '但是', '然而', '不过', '只是', '而且', '并且',
    # ── scene_l3.py STOPWORDS 词表（复用）──
    '就是', '然后', '已经', '还是', '没有', '不是', '一个', '一些', '有点', '的话',
    '的时候', '这样', '那样', '现在',
    # ── 对话高频虚词补充（八步分析真实垃圾样本）──
    '好的', '亲爱的', '问题', '对的', '最近的对', '我在', '爱的', '是吗', '好了',
    '好吧', '对吧', '是的', '了吗', '嗯嗯', '哈哈', '谢谢', '没事', '我现在', '我们现在',
    # ── 阶段B 补充：验收发现 '测试消息' 被提为高频标签；对话高频 2 字残片 ──
    '测试消息', '你是', '我是', '你的', '我的', '你说', '他说', '她说',
    '你在', '你给', '你们', '我们', '他们',
})

# 别名归一化表——V2.20.4 已知错误样本（来源: 八步分析 fact_tags 垃圾标签清单）。
# 值为规范标签；None 表示直接剔除。
_TAG_ALIASES = {
    '张三': '测试用户',      # 语音识别错字 → 正确人名
    '我在呢亲': '亲爱的',     # 口头问候残片 → 问候类（随后被停用词剔除）
    '爱的': '亲爱的',
    '亲爱的说': '亲爱的',
    '亲爱的的': '亲爱的',   # '亲爱的' 的 连写残片
    '聊成你在': None,         # 对话残片 → 直接剔除
    '刚忙完一': None,         # 事务叙述残片（刚忙完一点事情）→ 剔除
    '点事情': None,
    '你今天咋': None,         # 对话开头残片
    '你现在是': None,
    '每句话不': None,         # 提示词残片（每句话不超过X个字）
    '超过': None,
    '个字': None,
    '主人的女': None,         # 长句碎片（主人的女朋友）
    '的操作': None,           # 阶段B: 长句残片（安全的操作→碎成'的操作'）
    '你是聊天': None,         # 阶段B: 长句残片
    # ── 阶段B: 高频对话/人格样板残片（6月归档嵌入块，无信息量）──
    '对不对': None, '咋样呀': None, '样呀': None,
    '说话规则': None, '直奔主题': None, '主人说': None,
    '嘴要甜': None, '叫亲爱的': None, '你看一下': None,
    '不是助手': None, '速度测试': None,
}

# 标点/数字开头闸——逗号（标签分隔符）除外
_TAG_PUNCT_RE = re.compile(r'[：:【】\[\]()（）<>《》、。！？!?~～@#$%^&*_+=|\\/]')
_TAG_DIGIT_START_RE = re.compile(r'^\d')


def _tag_quality(tag: str):
    """V2.20.4 注入三道闸——返回 (是否通过, 归一化标签)。
    ①纯ASCII剔除（英文实体不进高频中文标签统计）
    ②中文停用词剔除
    ③长度闸 len 4~8（含）：纯中文2-3字实体名（测试用户/沙漏/记忆）是提取器原生组，豁免；
      超8字片段/1字残片出局；含标点或数字开头剔除。"""
    t = (tag or '').strip()
    if not t:
        return False, ''
    # 先归一化再过滤
    if t in _TAG_ALIASES:
        alias = _TAG_ALIASES[t]
        if alias is None:
            return False, ''
        t = alias
    if all(ord(c) < 128 for c in t):
        return False, ''
    if t in _TAG_STOPWORDS:
        return False, ''
    n = len(t)
    if n > 8:
        return False, ''
    if not (4 <= n <= 8):
        # 纯中文 2-3 字实体名豁免长度闸（提取器原生 2-4 字组）
        if not (2 <= n <= 3 and re.fullmatch(r'[\u4e00-\u9fff]{2,3}', t)):
            return False, ''
    if _TAG_PUNCT_RE.search(t) or _TAG_DIGIT_START_RE.match(t):
        return False, ''
    return True, t


# 内容特征前缀——system/tool/cron 注入块特征行（不按 role 硬切，按内容前缀特征）。
# 命中即标记为 system/tool 源：不参与 fact_tags 高频统计、提取时不落标签。
_SYSTEM_TOOL_PREFIXES = (
    '{', '[system', '[System', '<system>', '<tool>', '/system', '/tool', '/cron',
    '🧠', '🛠', '⚙', '🔧', '```',
)


def _content_part(line: str) -> str:
    """取 '|' 分隔后的正文段（sandglass.txt: 时间 | sender | 正文）；无分隔则整串。"""
    parts = line.split('|', 2)
    if len(parts) >= 3 and parts[0].strip() and parts[1].strip():
        return parts[2]
    return line


# 阶段B: 6月归档回显的【说话规则】【人格】提示词样板——系统提示回显，非用户信号，
# 参与统计会把'回正题/不要啰嗦/烦心事'等人格指令碎片顶进 top3
_PERSONA_ECHO_MARKERS = ('【说话规则】', '【人格】', '第一句就回正题')


def _is_system_tool_content(text: str) -> bool:
    """V2.20.4 内容特征判断——JSON工具输出/系统注记/注入块标记 归为 system/tool 源。
    阶段B 扩展：人格提示词样板回显（【说话规则】/【人格】）同样视为非用户信号源。"""
    if not text:
        return False
    if _content_part(text).strip().startswith(_SYSTEM_TOOL_PREFIXES):
        return True
    return any(m in text for m in _PERSONA_ECHO_MARKERS)


def _sandglass_lines() -> list:
    """当前沙漏全文行列表——行号门控 + 内容特征过滤的取数基准。"""
    try:
        from sandglass_paths import _SANDGLASS
        with open(_SANDGLASS, 'r', encoding='utf-8', errors='replace') as f:
            return f.readlines()
    except Exception:
        logger.warning(f"_sandglass_lines: 局部导入失败: from sandglass_paths import _SANDGLASS", exc_info=True)
        return []


def _sandglass_line_count() -> int:
    """当前沙漏物理行数（os.path 行数）——注入统计只取 ≤ 该行号的行。"""
    try:
        return len(_sandglass_lines())
    except Exception:
        return 0


def extract_tags(text: str, limit: int = 10) -> list:
    """V2.20.4 统一提取器——shadow_index / backfill / 重建共用。
    对 _ENTITY_RE 命中做 停用词/长度/ASCII 过滤 + 别名归一化；
    system/tool 注入块特征内容不提取标签。"""
    if not text or _is_system_tool_content(text):
        return []
    found = []
    for m in _ENTITY_RE.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3) or m.group(4) or m.group(5) or ""
        # 阶段B 残片闸：纯中文4字组若右侧紧邻汉字（长句被2-4字组切碎）或
        # 以口语代词/时间词开头（'你是刘浩'/'你说什么'/'今天很忙'/'你没看到'）→ 剔除；
        # 保留 代码审查员。 这类独立实体
        if (len(name) == 4 and re.fullmatch(r'[\u4e00-\u9fff]{4}', name)
                and ((m.end() < len(text) and '\u4e00' <= text[m.end()] <= '\u9fff')
                     or name.startswith(_TAG_FRAGMENT_4_PREFIXES))):
            continue
        ok, norm = _tag_quality(name)
        if ok:
            found.append(norm)
    seen, out = set(), []
    for t in found:
        if t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= limit:
            break
    return out


_conn = None
_conn_inode = None  # 连接建立时 shadow_sand.db 的 inode——文件被替换后靠它检测
_conn_lock = threading.Lock()

def _close_conn():
    """废弃当前连接（文件被替换/路径重定向时调用）。"""
    global _conn, _conn_inode
    c, _conn = _conn, None
    _conn_inode = None
    if c is not None:
        try:
            c.close()
        except Exception:
            logger.warning(f"_close_conn: 静默异常", exc_info=True)
            pass

def _db_inode() -> int:
    """当前磁盘上 shadow_sand.db 的 inode；文件不存在返回 0。"""
    try:
        return os.stat(_SHADOW_DB).st_ino
    except OSError:
        return 0

def _get_conn():
    global _conn, _conn_inode
    cur = _db_inode()
    if _conn is not None and _conn_inode is not None and cur != _conn_inode:
        # 磁盘文件已被替换/重建（inode 变了）→ 旧连接指向已删除的文件，必须重连
        _close_conn()
    if _conn is None:
        with _conn_lock:
            if _conn is None:
                _conn = sqlite3.connect(_SHADOW_DB, check_same_thread=False)
                _conn.execute("PRAGMA journal_mode=WAL")
                _conn.executescript(_SCHEMA)
                _conn.commit()
                _conn_inode = _db_inode()
    return _conn

def _maybe_commit():
    _get_conn().commit()  # V2.10.17: 每次写入立即commit,防崩溃丢数据


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


def shadow_max_trust() -> int:
    """trust 表最大行号——增量初始化断点。"""
    try:
        row = _get_conn().execute("SELECT COALESCE(MAX(line_num), 0) FROM trust").fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def shadow_top_tags(limit: int = 2000) -> list:
    """fact_tags 质量闸标签——V2.20.4 注入侧统一入口（__init__.py 与 memory_provider.py 共用）。
    行号门控：只取 line_num ≤ 当前沙漏物理行数（95.4% 越界残留直接出局）；
    内容特征：排除 system/tool/cron 注入块特征行（按内容前缀，不按 role 硬切）；
    三道闸：ASCII/中文停用词/长度标点 + 别名归一化。
    ORDER BY line_num DESC——让 LIMIT 覆盖最近行（fact_tags 无 per-tag COUNT 列，
    line_num DESC 即等价排序，配合 Python 侧 Counter 聚合）。"""
    try:
        cur_lines = _sandglass_line_count()
        if cur_lines <= 0:
            return []
        rows = _get_conn().execute(
            "SELECT line_num, tags FROM fact_tags "
            "WHERE tags != '' AND tags != '未分类' "
            "AND line_num > 0 AND line_num <= ? "
            "ORDER BY line_num DESC LIMIT ?",
            (cur_lines, limit)
        ).fetchall()
        lines = _sandglass_lines()
        out = []
        for ln, tags in rows:
            if 0 < ln <= len(lines) and _is_system_tool_content(lines[ln - 1]):
                continue  # system/tool 源注入块——不参与统计
            for t in tags.split(","):
                ok, norm = _tag_quality(t)
                if ok:
                    out.append(norm)
        # 冷沙归档标签——阶段B 重建后纳入统计（独立表，不占热沙行号，无越界）
        try:
            for (tags,) in _get_conn().execute(
                "SELECT tags FROM fact_tags_archive WHERE tags != '' AND tags != '未分类'"
            ).fetchall():
                for t in tags.split(","):
                    ok, norm = _tag_quality(t)
                    if ok:
                        out.append(norm)
        except Exception:
            logger.warning(f"shadow_top_tags: 静默异常", exc_info=True)
            pass
        return out
    except Exception:
        return []


def shadow_top_entities(limit: int = 5) -> list:
    """按关联行数降序取实体——system_prompt 实体注入用。"""
    try:
        return _get_conn().execute(
            "SELECT name, line_nums FROM entities "
            "WHERE length(name) >= 2 "
            "ORDER BY length(line_nums) - length(replace(line_nums,',','')) DESC "
            "LIMIT ?",
            (limit,)
        ).fetchall()
    except Exception:
        return []


def shadow_top_fact_categories(limit: int = 5) -> list:
    """fact_tags 分类明细——冲突6 system_prompt 事实标签块用。

    行号门控：只取 line_num <= 当前沙漏物理行数（越界历史残留直接出局）；
    内容特征：排除 system/tool/cron 注入块特征行；
    质量闸：每个 tag 走 _tag_quality；category 排除 general/exam_general/空/未分类。
    ORDER BY line_num DESC——最近分类优先；返回 [(category, tags), ...]。
    """
    try:
        cur_lines = _sandglass_line_count()
        if cur_lines <= 0:
            return []
        rows = _get_conn().execute(
            "SELECT line_num, category, tags FROM fact_tags "
            "WHERE category NOT IN ('general','exam_general','','未分类') "
            "AND tags != '' AND tags != '未分类' "
            "AND line_num > 0 AND line_num <= ? "
            "ORDER BY line_num DESC LIMIT ?",
            (cur_lines, limit)
        ).fetchall()
        lines = _sandglass_lines()
        out = []
        for ln, category, tags in rows:
            if 0 < ln <= len(lines) and _is_system_tool_content(lines[ln - 1]):
                continue  # system/tool 源注入块——不进入事实标签明细
            good = []
            for t in tags.split(","):
                ok, norm = _tag_quality(t)
                if ok:
                    good.append(norm)
            if good:
                out.append((category.strip() or "未分类", ",".join(good)))
        return out
    except Exception:
        logger.warning(f"shadow_top_fact_categories: 静默异常", exc_info=True)
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
    """落沙后同步——调用方传入实际行号，避免COUNT(*)偏移。V2.20.4: 统一走 extract_tags 质量闸。"""
    try:
        from sandglass_think import scene_mode
        if scene_mode() == 'exam': category = 'exam_' + category
    except Exception:
        logger.warning(f"shadow_index: 静默异常", exc_info=True)
        pass
    db = _get_conn()
    # V2.9.9.8: 行号由调用方传入，不自计数（防止与sandglass物理行号偏移）

    # V2.20.4: 统一提取器——停用词/长度/ASCII 过滤 + 别名归一化 + system/tool 内容跳过
    entities_found = extract_tags(text)
    for name in entities_found:
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

    # 兜底 tags：无 tags 时用实体名填充
    if not tags and entities_found:
        tags = ",".join(entities_found[:10])

    # 写入标签
    if category != "general" or tags:
        if category in ("general", "exam_general"):
            # V2.20.4: category 不再用首标签污染——空则 '未分类'，非空保持 general
            if not tags:
                category = "未分类"
        db.execute(
            "INSERT OR REPLACE INTO fact_tags (line_num, category, tags) VALUES (?, ?, ?)",
            (line_num, category, tags)
        )

    _maybe_commit()


def shadow_index_archive(text: str, category: str = "general") -> None:
    """冷沙归档标签——阶段B 重建：逐行走统一提取器，写入 fact_tags_archive 独立表。
    不占用热沙行号（归档内容在其归档文件中），无越界行号。"""
    try:
        if not text or _is_system_tool_content(text):
            return
        entities_found = extract_tags(text)
        if not entities_found:
            return
        db = _get_conn()
        db.execute(
            "INSERT INTO fact_tags_archive (category, tags) VALUES (?, ?)",
            (category, ",".join(entities_found[:10]))
        )
        _maybe_commit()
    except Exception:
        logger.warning(f"shadow_index_archive: 静默异常", exc_info=True)
        pass


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
