"""
NexSandglass 决策粒子提取器
=============================
从用户沙子里提炼决策粒子，喂给偏移率系统。
每粒 = (时间, 决策类型, 关键词, 偏移方向)
"""

import os, json, re
from datetime import datetime

_PARTICLES = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.jsonl")


def extract(user_message: str, ts: str = "") -> list:
    """从一条用户消息中提取决策粒子。返回 [{type, keyword, direction}]"""
    particles = []
    text = user_message.lower()

    # 决策类型检测
    checks = [
        # 选择型决策
        (r"(?:选|用|装|配|跑)\s*(.{2,20})(?:不选|不用|不装|不配)", "选择"),
        (r"还是(.+?)吧", "选择"),
        (r"就(.+?)了", "决定"),
        # 偏好型决策
        (r"我(?:喜欢|偏好|习惯|爱)\s*(.{2,30})", "偏好"),
        (r"我(?:讨厌|不喜欢|烦|受不了)\s*(.{2,30})", "禁区"),
        # 价值观决策
        (r"(免费|不花钱|自己搞|省钱|性价比|开源)", "省钱优先"),
        (r"(花钱|省事|付费|买|效率优先)", "效率优先"),
        # 红牌决策
        (r"(不管了|随便|放弃|能用就行|不纠结了|就这样)", "红牌"),
    ]

    for pattern, ptype in checks:
        m = re.search(pattern, text)
        if m:
            keyword = m.group(1).strip()[:20] if m.lastindex else pattern.strip("()")
            direction = {
                "省钱优先": "frugal",
                "效率优先": "spend",
                "红牌": "drift",
            }.get(ptype, "neutral")
            particles.append({
                "type": ptype,
                "keyword": keyword,
                "direction": direction,
            })

    return particles


def save(user_message: str, ts: str = "") -> list:
    """提取并保存决策粒子到本地。返回粒子列表。"""
    particles = extract(user_message, ts)
    if not particles:
        return []

    os.makedirs(os.path.dirname(_PARTICLES), exist_ok=True)
    for p in particles:
        p["ts"] = ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        p["source"] = user_message[:100]
        with open(_PARTICLES, "a", encoding="utf-8") as f:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    return particles


def load(limit: int = 50) -> list:
    """读取最近的决策粒子。"""
    if not os.path.exists(_PARTICLES):
        return []
    particles = []
    with open(_PARTICLES, "r", encoding="utf-8") as f:
        for line in f:
            try:
                particles.append(json.loads(line.strip()))
            except Exception:
                continue
    return particles[-limit:]


def stats() -> dict:
    """决策粒子统计——直接喂给偏移率。"""
    particles = load(100)
    if not particles:
        return {"total": 0, "frugal": 0, "spend": 0, "drift": 0}

    directions = {"frugal": 0, "spend": 0, "drift": 0, "neutral": 0}
    for p in particles:
        directions[p["direction"]] = directions.get(p["direction"], 0) + 1

    total = sum(directions.values())
    return {
        "total": total,
        "frugal": round(directions["frugal"] / total * 100) if total else 0,
        "spend": round(directions["spend"] / total * 100) if total else 0,
        "drift": round(directions["drift"] / total * 100) if total else 0,
    }
