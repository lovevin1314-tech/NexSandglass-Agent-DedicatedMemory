"""
NexSandglass 决策粒子 + 标签
=============================
第三层偏移率子系统。提取决策 → 打标签 → 喂灵魂蒸馏。
存储：纯文本。格式：时间 | 类型 | 关键词 | 方向 | 标签
"""

import os, re
from datetime import datetime

_PARTICLES = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")

# 内置标签映射
_TAG_MAP = {
    "选择": {
        "免费|不花钱|省钱|性价比|开源": ["成本观", "性价比优先"],
        "付费|买|花钱": ["成本观", "愿意投入"],
        "Python|Rust|Go|代码|工具": ["技术选型", "工具偏好"],
        "本地|离线|自建": ["架构偏好", "自托管"],
    },
    "偏好": {
        "开源|免费": ["技术价值观", "开源信徒"],
        "效率|快|简单": ["工作风格", "效率驱动"],
        "自己|手写|不靠": ["独立性", "动手派"],
    },
    "禁区": {
        "花钱|付费|订阅": ["成本底线"],
        "复杂|重|臃肿": ["技术审美", "极简主义"],
    },
    "省钱": {"*": ["成本观", "性价比优先"]},
    "花钱": {"*": ["成本观", "愿意投入"]},
    "红牌": {"*": ["决策疲劳", "需要休息"]},
}


def tag(particle_type: str, keyword: str) -> list:
    """给决策粒子打标签——连接偏移率和灵魂蒸馏。"""
    tags = []
    mappings = _TAG_MAP.get(particle_type, {})
    for pattern, tag_list in mappings.items():
        if pattern == "*" or any(w in keyword for w in pattern.split("|")):
            tags.extend(tag_list)
    return tags if tags else ["未分类"]


def extract(user_message: str) -> list:
    """从用户消息中提取决策粒子。"""
    particles = []
    text = user_message.lower()
    checks = [
        (r"(?:选|用|装|配|跑)\s*(.{2,20})(?:不选|不用|不装|不配|吧)", "选择"),
        (r"还是(.+?)吧", "选择"),
        (r"就(.+?)了", "决定"),
        (r"我(?:喜欢|偏好|习惯|爱)\s*(.{2,30})", "偏好"),
        (r"我(?:讨厌|不喜欢|烦|受不了)\s*(.{2,30})", "禁区"),
        (r"(免费|不花钱|自己搞|省钱|性价比|开源)", "省钱"),
        (r"(花钱|省事|付费|买|效率优先)", "花钱"),
        (r"(不管了|随便|放弃|能用就行|不纠结|就这样)", "红牌"),
    ]
    for pattern, ptype in checks:
        m = re.search(pattern, text)
        if m:
            kw = m.group(1).strip()[:20]
            direction = {"省钱": "frugal", "花钱": "spend", "红牌": "drift"}.get(ptype, "neutral")
            tags = tag(ptype, kw)
            particles.append((ptype, kw, direction, ",".join(tags)))
    return particles


def log(user_message: str, ts: str = "") -> int:
    """提取并落盘决策粒子。"""
    particles = extract(user_message)
    if not particles:
        return 0
    if not ts:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(_PARTICLES), exist_ok=True)
    with open(_PARTICLES, "a", encoding="utf-8") as f:
        for ptype, kw, direction, tags in particles:
            f.write(f"{ts} | {ptype} | {kw} | {direction} | {tags}\n")
    return len(particles)


def read(limit: int = 100) -> list:
    """读取最近决策粒子。"""
    if not os.path.exists(_PARTICLES):
        return []
    with open(_PARTICLES, "r", encoding="utf-8") as f:
        lines = f.readlines()
    particles = []
    for line in lines[-limit:]:
        parts = line.strip().split(" | ")
        if len(parts) >= 4:
            particles.append(tuple(parts))
    return particles


def ratio() -> dict:
    """决策粒子偏移比。"""
    particles = read(50)
    if not particles:
        return {"frugal": 0, "spend": 0, "drift": 0, "total": 0}
    counts = {"frugal": 0, "spend": 0, "drift": 0}
    for p in particles:
        d = p[3] if len(p) > 3 else "neutral"
        if d in counts:
            counts[d] += 1
    total = sum(counts.values())
    return {
        "total": total,
        "frugal_pct": round(counts["frugal"]/total*100) if total else 0,
        "spend_pct": round(counts["spend"]/total*100) if total else 0,
        "drift_pct": round(counts["drift"]/total*100) if total else 0,
    }
