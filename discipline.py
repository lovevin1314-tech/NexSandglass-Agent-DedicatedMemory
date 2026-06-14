"""
NexSandglass L3 — 纪律因子 (V2.9.6: 权重计数)
从 sandglass_think.py 拆分。
"""
import os, json
from collections import Counter

from sandglass_paths import _NB
_IRON_RULES = os.path.join(_NB, "iron_rules.txt")
_RULE_COUNTS = os.path.join(_NB, "persona", "rule_counts.json")


def _load_counts() -> dict:
    """加载规则计数"""
    if not os.path.exists(_RULE_COUNTS):
        return {}
    with open(_RULE_COUNTS, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_counts(counts: dict):
    """保存规则计数"""
    os.makedirs(os.path.dirname(_RULE_COUNTS), exist_ok=True)
    with open(_RULE_COUNTS, "w", encoding="utf-8") as f:
        json.dump(counts, f, ensure_ascii=False)


def iron_rules(limit: int = 3) -> list:
    """读取纪律——按提醒次数排序，最多 limit 条。"""
    if not os.path.exists(_IRON_RULES):
        return []
    raw = [l.strip() for l in open(_IRON_RULES, "r", encoding="utf-8").readlines() if l.strip()]
    counts = _load_counts()
    # 排序：计数高的在前，未计数过的放后面
    scored = sorted(raw, key=lambda r: counts.get(r, 0), reverse=True)
    return scored[:limit]


def iron_rules_with_counts(limit: int = 3) -> list:
    """读取纪律——带计数，用于注入。返回 [(rule, count), ...]"""
    rules = iron_rules(limit)
    counts = _load_counts()
    return [(r, counts.get(r, 0)) for r in rules]


def iron_rule_bump(rule_text: str):
    """提醒计数 +1——每次 LLM 引用/提醒某条规则时调用"""
    if not os.path.exists(_IRON_RULES):
        return
    raw = [l.strip() for l in open(_IRON_RULES, "r", encoding="utf-8").readlines() if l.strip()]
    for r in raw:
        if r.lower() in rule_text.lower() or rule_text.lower() in r.lower():
            counts = _load_counts()
            counts[r] = counts.get(r, 0) + 1
            _save_counts(counts)
            return


# V2.9.9: 会话级去重——注入时每条规则每session只bump一次
_injected_this_session = set()

def iron_rule_inject_bump(rule_text: str):
    """注入时bump——去重，每条规则每session只+1"""
    key = rule_text.strip().lower()
    if key in _injected_this_session:
        return
    _injected_this_session.add(key)
    iron_rule_bump(rule_text)


def iron_rules_set(rules: list) -> bool:
    """设定纪律。覆盖写入，最多5条。"""
    os.makedirs(os.path.dirname(_IRON_RULES), exist_ok=True)
    with open(_IRON_RULES, "w", encoding="utf-8") as f:
        for r in rules[:5]:
            f.write(r[:200] + "\n")
    return True
