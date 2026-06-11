"""
NexSandglass L3 — 纪律因子
从 sandglass_think.py 拆分。
"""
import os

from sandglass_paths import _NB
_IRON_RULES = os.path.join(_NB, "iron_rules.txt")


def iron_rules() -> list:
    """读取用户设定的纪律——绝不违反的规则。最多5条。"""
    if not os.path.exists(_IRON_RULES):
        return []
    with open(_IRON_RULES, "r", encoding="utf-8") as f:
        return [l.strip() for l in f.readlines() if l.strip()][:5]


def iron_rules_set(rules: list) -> bool:
    """设定纪律。覆盖写入，最多5条。"""
    os.makedirs(os.path.dirname(_IRON_RULES), exist_ok=True)
    with open(_IRON_RULES, "w", encoding="utf-8") as f:
        for r in rules[:5]:
            f.write(r[:200] + "\n")
    return True
