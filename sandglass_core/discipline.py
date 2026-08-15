"""
NexSandglass L3 — 铁律因子 (V2.9.6: 权重计数)
从 sandglass_think.py 拆分。
"""
import os, json, re
from datetime import datetime
from collections import Counter

from sandglass_paths import _NB
_IRON_RULES = os.path.join(_NB, "iron_rules.txt")
_RULE_COUNTS = os.path.join(_NB, "persona", "rule_counts.json")
_CANDIDATE_PREFIX = "[candidate] "
_RED_PREFIX = "[red] "
_NORMAL_PREFIX = "[normal] "
_RED_VIOLATION_THRESHOLD = 2
# 预算单位：估算 token（零 LLM 纯本地；中文≈1字1token，ASCII连续段≈1token）。
_RED_TOKEN_BUDGET = 250
_NORMAL_TOKEN_BUDGET = 50

_CJK_RE = re.compile(
    r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]"
)
_ASCII_RUN_RE = re.compile(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*")

# 触发词自动扩展：命中左列关键词时，把右列同义/相关动作词一并视为触发词。
_RULE_TRIGGER_GROUPS = [
    ("镜像", ["镜像", "GitHub", "github", "pull", "clone", "下载", "更新", "直连"]),
    ("github", ["GitHub", "github", "pull", "clone", "下载", "更新", "直连", "镜像"]),
    ("pull", ["pull", "clone", "GitHub", "github", "下载", "更新"]),
    ("clone", ["clone", "pull", "GitHub", "github", "下载", "更新"]),
    ("下载", ["下载", "GitHub", "github", "clone", "直连"]),
    ("更新", ["更新", "GitHub", "github", "pull", "下载"]),
    ("直连", ["直连", "GitHub", "github", "下载", "镜像"]),
    ("测试", ["测试", "跑测试", "改代码"]),
    ("代码", ["代码", "改代码", "测试"]),
    ("沙漏", ["沙漏", "临时沙漏", "sandglass", "搜索"]),
    ("本地", ["本地", "本地搜索", "沙漏", "搜索"]),
]


def _load_counts() -> dict:
    """加载规则计数；旧格式自动迁移为新多维结构。

    旧格式：{"规则全文": 81}
    新格式：{"规则全文": {"inject_count": 81, "remind_count": 0,
                           "violation_count": 0, "last_source_line": null,
                           "updated_at": "..."}}
    """
    if not os.path.exists(_RULE_COUNTS):
        return {}
    with open(_RULE_COUNTS, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        return {}

    needs_migration = any(not isinstance(value, dict) for value in raw.values())
    counts = {key: _normalize_count_entry(value) for key, value in raw.items()}
    if needs_migration:
        _save_counts(counts)
    return counts


def _save_counts(counts: dict):
    """保存规则计数"""
    os.makedirs(os.path.dirname(_RULE_COUNTS), exist_ok=True)
    with open(_RULE_COUNTS, "w", encoding="utf-8") as f:
        json.dump(counts, f, ensure_ascii=False)


def _now_iso() -> str:
    """返回当前时间 ISO 字符串。"""
    return datetime.now().isoformat(timespec="seconds")


def _new_count_entry(inject_count=0, remind_count=0, violation_count=0,
                     last_source_line=None, updated_at=None):
    """构造一条规则计数条目。

    字段语义：
    - inject_count：注入次数（历史保留，不再作为排序唯一依据）
    - remind_count：主人/LLM 实际引用提醒该规则的次数（真实事件）
    - violation_count：确认违规次数
    - last_source_line：最近一次触发来源沙号（溯源）
    - updated_at：最后更新时间
    """
    return {
        "inject_count": int(inject_count or 0),
        "remind_count": int(remind_count or 0),
        "violation_count": int(violation_count or 0),
        "last_source_line": last_source_line,
        "updated_at": updated_at or "",
    }


def _normalize_count_entry(value):
    """把旧整数或新 dict 归一化为多维条目。"""
    if isinstance(value, dict):
        return _new_count_entry(
            inject_count=value.get("inject_count", 0),
            remind_count=value.get("remind_count", 0),
            violation_count=value.get("violation_count", 0),
            last_source_line=value.get("last_source_line"),
            updated_at=value.get("updated_at") or "",
        )
    try:
        legacy = int(value)
    except (TypeError, ValueError):
        legacy = 0
    return _new_count_entry(
        inject_count=legacy,
        updated_at=_now_iso(),
    )


def _count_int(entry: dict, field: str) -> int:
    """安全读取整数字段。"""
    try:
        return int((entry or {}).get(field, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _rule_priority_score(entry: dict) -> int:
    """排序分：inject_count 保留历史权重 1，remind_count 作为真实信号权重 3。

    理由：remind/violation 是真实行为信号，应比历史注入假计数更快影响排序；
    同时 inject_count=1 的权重让旧 81 条相对 0 分新规则仍稳定排前。
    """
    if not entry:
        return 0
    return _count_int(entry, "inject_count") * 1 + _count_int(entry, "remind_count") * 3


def _read_rule_lines():
    """读取 iron_rules.txt 全部非空行。"""
    if not os.path.exists(_IRON_RULES):
        return []
    with open(_IRON_RULES, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _active_rule_lines():
    """只读 active 行；[candidate] 候选行不参与注入。"""
    return [line for line in _read_rule_lines() if not line.startswith(_CANDIDATE_PREFIX)]


def _normalize_candidate_text(value):
    """候选正文归一化，用于去重。"""
    return re.sub(r"\s+", " ", value or "").strip(" ，。！？!?；;")


def _parse_rule_line(line: str) -> dict:
    """把 active 行解析为结构化规则。

    支持三种写法（旧行自动视为 normal）：
    - 无标记旧行：``规则正文``
    - 前缀标记：``[red] 规则正文`` / ``[normal] 规则正文``
    - 前缀 + JSON：``[red] {"text": "...", "trigger_words": ["镜像"]}``
    """
    raw = (line or "").strip()
    level_mark = None
    payload = raw
    for mark, prefix in (("red", _RED_PREFIX), ("normal", _NORMAL_PREFIX)):
        if raw.startswith(prefix):
            level_mark = mark
            payload = raw[len(prefix):].strip()
            break

    text = payload
    manual_triggers = []
    if payload.startswith("{"):
        try:
            data = json.loads(payload)
        except Exception:
            data = None
        if isinstance(data, dict):
            text = str(data.get("text") or "").strip()
            triggers = data.get("trigger_words") or data.get("triggers") or []
            if isinstance(triggers, str):
                triggers = [triggers]
            manual_triggers = [str(x).strip() for x in triggers if str(x).strip()]
    if not text:
        text = payload
    return {
        "raw": raw,
        "level_mark": level_mark,
        "text": text.strip(),
        "manual_triggers": manual_triggers,
    }


def _active_rule_infos() -> list:
    """读取 active 规则结构；[candidate] 候选行不参与。"""
    return [
        _parse_rule_line(line)
        for line in _read_rule_lines()
        if not line.startswith(_CANDIDATE_PREFIX)
    ]


def _find_count_key(counts: dict, info: dict):
    """按正文或原始行查计数 key，兼容旧 key 和新增前缀 key。"""
    text = info.get("text", "").strip()
    raw = info.get("raw", "").strip()
    for key in (text, raw):
        if key and key in counts:
            return key
    lowered = text.lower()
    for key in counts:
        try:
            if _parse_rule_line(key).get("text", "").strip().lower() == lowered:
                return key
        except Exception:
            continue
    return None


def _entry_for_rule(counts: dict, info: dict):
    """取一条规则的计数条目；无计数时返回空 dict。"""
    key = _find_count_key(counts, info)
    return counts.get(key) if key else {}


def _rule_violation_count(entry: dict) -> int:
    """读取违规次数。"""
    return _count_int(entry, "violation_count")


def _auto_trigger_words(text: str) -> list:
    """从规则文本自动生成触发词（简单子串匹配，零外部依赖）。"""
    words = set()
    lowered = (text or "").lower()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9._-]{1,}", text or ""):
        words.add(token)
        words.add(token.lower())
    for needle, expanded in _RULE_TRIGGER_GROUPS:
        if needle.lower() in lowered:
            words.update(expanded)
    # 去掉常见的规则句式功能词后再提取中文片段，避免把整句当触发词。
    for chunk in re.split(r"该走|以后|禁止|必须|应该|不得|不要|每次|自动|直接|先|再|要|得|走", text or ""):
        for term in re.findall(r"[一-鿿]{2,12}", chunk):
            words.add(term)
    normalized = _normalize_candidate_text(text)
    if 2 <= len(normalized) <= 16:
        words.add(normalized)
    return sorted(words, key=lambda x: (x.lower(), len(x)))


def _rule_trigger_words(info: dict) -> list:
    """自动生成触发词，并合并人工补充。"""
    auto = _auto_trigger_words(info.get("text", ""))
    manual = info.get("manual_triggers") or []
    return sorted(set(auto) | set(manual), key=lambda x: (x.lower(), len(x)))


def _first_trigger_hit(trigger_words: list, context: str):
    """返回上下文命中的第一个触发词；未命中返回 None。"""
    if not trigger_words:
        return None
    ctx = (context or "").lower()
    for word in trigger_words:
        if word and word.lower() in ctx:
            return word
    return None


def _estimate_tokens(text: str) -> int:
    """零 LLM 纯本地 token 估算（用于预算截断，非精确 BPE）。

    规则：
    - CJK 单字 ≈ 1 token（中文 1 字≈1 token）；
    - 拉丁字母/数字连续段 ≈ 1 token；
    - 其余非空白符号每个 ≈ 1 token。
    """
    if not text:
        return 0
    text = str(text)
    tokens = len(_CJK_RE.findall(text))
    without_cjk = _CJK_RE.sub(" ", text)
    tokens += len(_ASCII_RUN_RE.findall(without_cjk))
    leftover = _ASCII_RUN_RE.sub("", without_cjk)
    tokens += len(re.sub(r"\s+", "", leftover))
    return max(1, tokens)


def _red_line_estimate(text: str, score: int) -> int:
    """红牌注入行的 token 估算（与 __init__ 实际渲染格式一致）。"""
    return _estimate_tokens(f"[red] {text} ×{score}")


def _normal_line_estimate(text: str, score: int, triggered_by) -> int:
    """普通注入行的 token 估算（与 __init__ 实际渲染格式一致）。"""
    return _estimate_tokens(f"[normal] {text} ×{score} [触发:{triggered_by}]")


def _budget_slice(items: list, budget: int, estimate) -> tuple:
    """按单条估算 token 做预算截断；超预算的单条不纳入。"""
    out = []
    used = 0
    for item in items:
        cost = int(estimate(item))
        if cost > budget:
            continue
        if out and used + cost > budget:
            continue
        out.append(item)
        used += cost
    return out, used


def iron_rule_layers(context: str = "") -> dict:
    """双层铁律注入选择器（零 LLM，纯本地）。

    - 红牌池：手动 [red] 或 violation_count >= 2 自动升红；常驻注入。
    - 普通池：只有 context 命中 trigger_words 才注入。
    - 排序只在池内进行：红牌按 violation_count 降序，普通按 inject×1+remind×3 降序。
    """
    counts = _load_counts()
    red_items = []
    normal_items = []

    for info in _active_rule_infos():
        entry = _entry_for_rule(counts, info)
        score = _rule_priority_score(entry)
        violation_count = _rule_violation_count(entry)
        trigger_words = _rule_trigger_words(info)
        is_red = info.get("level_mark") == "red" or violation_count >= _RED_VIOLATION_THRESHOLD
        if is_red:
            red_items.append({
                "text": info["text"],
                "level": "red",
                "score": score,
                "violation_count": violation_count,
                "trigger_words": trigger_words,
                "triggered_by": None,
                "raw": info["raw"],
            })
            continue

        triggered_by = _first_trigger_hit(trigger_words, context)
        if triggered_by:
            normal_items.append({
                "text": info["text"],
                "level": "normal",
                "score": score,
                "violation_count": violation_count,
                "trigger_words": trigger_words,
                "triggered_by": triggered_by,
                "raw": info["raw"],
            })

    red_items.sort(key=lambda item: item["violation_count"], reverse=True)
    normal_items.sort(key=lambda item: item["score"], reverse=True)

    red_items, red_used = _budget_slice(
        red_items,
        _RED_TOKEN_BUDGET,
        lambda item: _red_line_estimate(item["text"], item["score"]),
    )
    normal_items, normal_used = _budget_slice(
        normal_items,
        _NORMAL_TOKEN_BUDGET,
        lambda item: _normal_line_estimate(item["text"], item["score"], item["triggered_by"]),
    )

    return {
        "red": red_items,
        "normal": normal_items,
        "token_est": {
            "red_tokens": red_used,
            "normal_tokens": normal_used,
            "total_tokens": red_used + normal_used,
            # 兼容旧字段名；单位已从“字符”改为“估算 token”。
            "red_chars": red_used,
            "normal_chars": normal_used,
            "total_chars": red_used + normal_used,
        },
    }


def iron_rule_inject_texts(context: str = "") -> list:
    """返回本次实际注入的规则正文，供调用方 bump inject_count。"""
    layers = iron_rule_layers(context)
    return [item["text"] for item in layers["red"] + layers["normal"]]


def iron_rules(limit: int = 3) -> list:
    """旧接口兼容：返回按多维优先级排序的规则正文，最多 limit 条。

    新注入逻辑请使用 iron_rule_layers()；本函数仅保留展示/兼容用途。
    """
    if not os.path.exists(_IRON_RULES):
        return []
    infos = _active_rule_infos()
    if not infos:
        return []
    counts = _load_counts()
    scored = sorted(
        infos,
        key=lambda info: _rule_priority_score(_entry_for_rule(counts, info)),
        reverse=True,
    )
    return [info["text"] for info in scored[:limit]]


def iron_rules_with_counts(limit: int = 3) -> list:
    """旧接口兼容：读取铁律并带优先级分。

    该读取路径只排序/展示，不做任何 bump；注入计数由调用方在真正写入
    system prompt 后显式调用 iron_rule_inject_bump()。
    """
    rules = iron_rules(limit)
    counts = _load_counts()
    return [
        (rule, _rule_priority_score(_entry_for_rule(counts, _parse_rule_line(rule))))
        for rule in rules
    ]


def iron_rule_bump(rule_text: str, field: str = "remind_count", source_line=None):
    """按真实事件 bump 铁律计数。

    - field 默认 remind_count；允许 violation_count。
    - source_line 非 None 时写入 last_source_line，用于溯源。
    - 不触碰 inject_count，注入历史由 iron_rule_inject_bump() 单独维护。
    """
    if field not in ("remind_count", "violation_count"):
        return
    if not os.path.exists(_IRON_RULES):
        return
    infos = _active_rule_infos()
    for info in infos:
        text = info["text"]
        if text.lower() in rule_text.lower() or rule_text.lower() in text.lower():
            counts = _load_counts()
            key = _find_count_key(counts, info) or text
            entry = _normalize_count_entry(counts.get(key))
            entry[field] = _count_int(entry, field) + 1
            if source_line is not None:
                entry["last_source_line"] = int(source_line)
            entry["updated_at"] = _now_iso()
            counts[key] = entry
            _save_counts(counts)
            return


# V2.9.9: 会话级去重——注入时每条规则每 session 只 bump 一次；
# V2.20.x: 提供 session 结束重置入口，避免模块级 set 永久只增不删。
_injected_this_session = set()

def iron_rule_inject_bump(rule_text: str):
    """真实注入计数 +1，只碰 inject_count。

    每条规则在一个会话内去重，重复调用不重复计数；会话结束调用
    iron_rule_session_reset() 清空，下一会话可重新计数。
    """
    key = rule_text.strip().lower()
    if key in _injected_this_session:
        return
    if not os.path.exists(_IRON_RULES):
        return
    infos = _active_rule_infos()
    for info in infos:
        text = info["text"]
        if text.lower() in rule_text.lower() or rule_text.lower() in text.lower():
            _injected_this_session.add(key)
            counts = _load_counts()
            key = _find_count_key(counts, info) or text
            entry = _normalize_count_entry(counts.get(key))
            entry["inject_count"] = _count_int(entry, "inject_count") + 1
            entry["updated_at"] = _now_iso()
            counts[key] = entry
            _save_counts(counts)
            return


def iron_rule_session_reset():
    """会话结束时清空注入去重集合，允许下一会话重新统计 inject_count。"""
    _injected_this_session.clear()


def iron_rules_set(rules: list) -> bool:
    """设定铁律。覆盖写入，最多5条。"""
    os.makedirs(os.path.dirname(_IRON_RULES), exist_ok=True)
    with open(_IRON_RULES, "w", encoding="utf-8") as f:
        for r in rules[:5]:
            f.write(r[:200] + "\n")
    return True


# ── 断点1：铁律提取闭环（纯正则，候选不注入） ──────────────────

_EXTRACT_PATTERNS = [
    # 该走X走X：该走镜像走镜像
    (re.compile(r"该走(.{1,20}?)走\1"), "该走X走X", True),
    # 以后X要Y：以后改代码要先跑测试
    (re.compile(r"以后(.{1,30}?)(?:要|必须|应该|得)(.{1,80}?)(?=[，。！？!?；;]|$)"), "以后X要Y", True),
    # 以后X（兜底）：以后先搜本地再动手
    (re.compile(r"以后(.{1,80}?)(?=[，。！？!?；;]|$)"), "以后X", True),
    # 禁止X：禁止直连GitHub
    (re.compile(r"禁止(.{1,60}?)(?=[，。！？!?；;]|$)"), "禁止X", True),
    # User correction during the turn: <正文>
    (re.compile(r"User correction during the turn:\s*(.{1,200})", re.IGNORECASE), "user_correction", False),
]


def iron_rule_extract_candidates(text, source_line=0, created_at=None):
    """从主人句式正则提取候选铁律。

    返回结构化候选列表：
        text, source_line, level='candidate', created_at
    """
    if not text:
        return []
    text = text.replace("\r", " ").replace("\n", " ").strip()
    created_at = created_at or datetime.now().isoformat(timespec="seconds")
    seen = set()
    candidates = []
    for pattern, name, use_full_match in _EXTRACT_PATTERNS:
        for match in pattern.finditer(text):
            body = match.group(0) if use_full_match else match.group(1)
            body = _normalize_candidate_text(body)
            if not body:
                continue
            key = body.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                "text": body,
                "source_line": int(source_line or 0),
                "level": "candidate",
                "created_at": created_at,
                "pattern": name,
            })
    return candidates


def iron_rule_candidates():
    """读取 iron_rules.txt 中 [candidate] 候选区，返回结构化字段列表。"""
    out = []
    for line in _read_rule_lines():
        if not line.startswith(_CANDIDATE_PREFIX):
            continue
        payload = line[len(_CANDIDATE_PREFIX):].strip()
        try:
            data = json.loads(payload)
        except Exception:
            data = {
                "text": payload,
                "source_line": 0,
                "level": "candidate",
                "created_at": "",
            }
        data.setdefault("level", "candidate")
        out.append(data)
    return out


def iron_rule_append_candidate(candidate):
    """追加一条候选；text 归一化相同视为重复，不重复追加。"""
    text = _normalize_candidate_text((candidate or {}).get("text", ""))
    if not text:
        return False
    for existing in iron_rule_candidates():
        if _normalize_candidate_text(existing.get("text", "")).lower() == text.lower():
            return False
    payload = {
        "text": text,
        "source_line": int((candidate or {}).get("source_line") or 0),
        "level": "candidate",
        "created_at": (candidate or {}).get("created_at") or datetime.now().isoformat(timespec="seconds"),
    }
    os.makedirs(os.path.dirname(_IRON_RULES), exist_ok=True)
    with open(_IRON_RULES, "a", encoding="utf-8") as f:
        f.write(_CANDIDATE_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
    return True


def iron_rule_extract_and_store(text, source_line=0):
    """被动触发入口：提取并写入候选区，返回本次新增条数。"""
    added = 0
    for candidate in iron_rule_extract_candidates(text, source_line):
        if iron_rule_append_candidate(candidate):
            added += 1
    return added
