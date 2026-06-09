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
    # 反哺第三层四支柱
    feed_all(question, tags, choice, direction)


def read(limit: int = 50) -> list:
    """读最近决策粒子。"""
    if not os.path.exists(_PARTICLES):
        return []
    with open(_PARTICLES, "r", encoding="utf-8") as f:
        return [l.strip().split(" | ") for l in f.readlines()[-limit:]]


def feed_persona(particle_type: str, tags: str, keyword: str) -> None:
    """决策粒子反哺灵魂蒸馏——更新画像认知内核。"""
    persona_path = os.path.join(os.path.expanduser("~"), ".neurobase", "persona", "persona.md")
    if not os.path.exists(persona_path):
        return
    with open(persona_path, "r", encoding="utf-8") as f:
        content = f.read()
    layer_map = {"成本观":"🔴 认知内核","性价比优先":"🔴 认知内核","技术选型":"🔵 兴趣图谱","工具偏好":"🔵 兴趣图谱","独立性":"🔴 认知内核","动手派":"🔴 认知内核","决策疲劳":"🟡 交互协议","红牌":"🟡 交互协议","极简主义":"🟡 交互协议","开源信徒":"🔵 兴趣图谱"}
    added = []
    for tag in tags.split(","):
        tag = tag.strip()
        if layer_map.get(tag) and tag not in content:
            added.append(f"- [{datetime.now():%Y-%m-%d}] {tag}（决策粒子提炼）")
    if added:
        insert = content.find("## 🔴 认知内核")
        if insert < 0: insert = len(content)
        new = content[:insert] + "\n".join(added) + "\n" + content[insert:]
        with open(persona_path, "w", encoding="utf-8") as f: f.write(new)


def feed_all(question: str, choice: str, tags: str, direction: str) -> None:
    """决策粒子喂第三层四支柱。"""
    feed_persona(question, tags, choice)           # 🧬 灵魂蒸馏
    _update_search_weights(tags)                    # ⏳ 时间检索
    _weave_check(tags, choice)                      # 🧵 织布机
    # 📊 偏移率 — 粒子落盘即计数，ratio() 直接读


def _update_search_weights(tags: str) -> None:
    """时间检索：高频标签→搜索权重缓存。"""
    wf = os.path.join(os.path.expanduser("~"), ".neurobase", "search_weights.txt")
    weights = {}
    if os.path.exists(wf):
        with open(wf, "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    k, v = line.strip().split(":", 1)
                    weights[k] = int(v)
    for tag in tags.split(","):
        tag = tag.strip()
        weights[tag] = weights.get(tag, 0) + 1
    with open(wf, "w", encoding="utf-8") as f:
        for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True)[:20]:
            f.write(f"{k}:{v}\n")


def _weave_check(tags: str, choice: str) -> None:
    """织布机：决策粒子与画像矛盾检测。"""
    p = os.path.join(os.path.expanduser("~"), ".neurobase", "persona", "persona.md")
    if not os.path.exists(p): return
    with open(p, "r", encoding="utf-8") as f: persona = f.read()
    contra = []
    if "成本观" in tags and "性价比优先" in persona and "spend" in _direction(choice):
        contra.append("画像:性价比优先 ↔ 决策:愿意投入")
    if "决策疲劳" in tags and "追根溯源" in persona:
        contra.append("画像:追根溯源 ↔ 决策:红牌放弃")
    if contra:
        wl = os.path.join(os.path.expanduser("~"), ".neurobase", "weave_alerts.txt")
        with open(wl, "a", encoding="utf-8") as f:
            for c in contra:
                f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {c}\n")


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
