"""
NexSandglass 决策粒子
=====================
只记：时间 | 问题 | 选择 | 方向 | 标签
脉冲神经信号——驱动偏移率检测和灵魂蒸馏。
"""

import os, re
from datetime import datetime

_PARTICLES = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")

_TAG_MAP = {
    "免费|不花钱|省钱|性价比|开源": ["成本观", "性价比优先"],
    "付费|买|花钱|效率优先": ["成本观", "愿意投入"],
    "Python|Rust|Go|代码": ["技术选型", "工具偏好"],
    "自己|手写|不靠|本地|离线": ["独立性", "动手派"],
    "不管了|随便|放弃|不纠结": ["决策疲劳", "红牌"],
}


def _tag(choice: str, question: str = "") -> str:
    """双模标签：本地关键词 → LLM提炼。"""
    # 本地标签
    tags = []
    for pattern, tag_list in _TAG_MAP.items():
        if any(w in choice for w in pattern.split("|")):
            tags.extend(tag_list)
    if tags:
        return ",".join(tags)  # 本地标签

    # LLM 提炼标签
    try:
        import os as _os, urllib.request as _ur, json as _json
        key = _os.environ.get("DEEPSEEK_API_KEY", "") or _os.environ.get("OPENROUTER_API_KEY", "")
        if key:
            body = _json.dumps({"model":"deepseek-chat","messages":[
                {"role":"system","content":"你是决策分析器。用户做了一个选择，分析其深层动机和价值观。返回2-3个标签，逗号分隔。例如：成本观,独立性,技术审美。只返回标签。"},
                {"role":"user","content": f"问题：{question}\n选择：{choice}"}
            ],"max_tokens":50,"temperature":0.2}).encode()
            req = _ur.Request("https://api.deepseek.com/v1/chat/completions", data=body,
                headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
            resp = _ur.urlopen(req, timeout=10)
            result = _json.loads(resp.read())["choices"][0]["message"]["content"]
            return result.strip()
    except Exception:
        pass

    return "未分类"


def _direction(choice: str) -> str:
    if any(w in choice for w in ["免费","不花钱","省钱","性价比","开源","自己搞","本地"]):
        return "frugal"
    if any(w in choice for w in ["花钱","付费","买","效率优先"]):
        return "spend"
    if any(w in choice for w in ["不管了","随便","放弃","不纠结"]):
        return "drift"
    return "neutral"


def log(question: str, choice: str, ts: str = "") -> None:
    """落一粒决策。问题 + 最终选择 + 自动标签。"""
    if not ts:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tags = _tag(choice, question)
    direction = _direction(choice)
    os.makedirs(os.path.dirname(_PARTICLES), exist_ok=True)
    with open(_PARTICLES, "a", encoding="utf-8") as f:
        f.write(f"{ts} | {question[:80]} | {choice[:40]} | {direction} | {tags}\n")


def read(limit: int = 50) -> list:
    """读最近决策粒子。"""
    if not os.path.exists(_PARTICLES):
        return []
    with open(_PARTICLES, "r", encoding="utf-8") as f:
        return [l.strip().split(" | ") for l in f.readlines()[-limit:]]


def ratio() -> dict:
    """偏移比——直接喂偏移率。"""
    particles = read(50)
    if not particles: return {"frugal":0,"spend":0,"drift":0,"total":0}
    counts = {"frugal":0,"spend":0,"drift":0}
    for p in particles:
        d = p[3] if len(p)>3 else "neutral"
        if d in counts: counts[d] += 1
    total = sum(counts.values())
    return {"frugal": round(counts["frugal"]/total*100) if total else 0,
            "spend": round(counts["spend"]/total*100) if total else 0,
            "drift": round(counts["drift"]/total*100) if total else 0,
            "total": total}
