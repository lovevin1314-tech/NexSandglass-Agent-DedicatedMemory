"""丘脑层 L2 — 魔镜架构。反射脑干+ L3数据，格式化给Hermes注入。"""
import os
from sandglass_paths import _NB
from brainstem import recent as bs_recent, total as bs_total, triples as bs_triples

def _fmt_line(k, v, limit=40):
    v = v[:limit]
    return f"{k}: {v}"

def mirror_static():
    """魔镜·静 — 每会话一次性注入"""
    lines = []
    t = bs_total()
    lines.append(f"沙漏: {t}条")
    tr = bs_triples()
    if tr:
        lines.append(f"三元组: {len(tr)}条")
    return "\n".join(lines)

def mirror_dynamic():
    """魔镜·动 — 每轮增量注入(反射L3情绪熵+偏移)"""
    lines = []
    try:
        import sys, os as _os
        _core = _os.path.join(_os.path.dirname(__file__), "..", "sandglass_core")
        sys.path.insert(0, _core)
        # 情绪熵
        try:
            from emotion_vocab import detect as _em_detect
            r = _em_detect("")
            if r and r.get("mood"):
                mood = r["mood"]
                tip = {"开心":"","焦虑":"—安静陪着","愤怒":"—不催","悲伤":"—不打扰"}.get(mood,"")
                lines.append(f"🎭 {mood}{tip}")
        except Exception:
            pass
        # 偏移率
        try:
            from offset_l3 import comprehensive_offset
            co = comprehensive_offset()
            if co and co.get("offset"):
                d = co["direction"]
                o = co["offset"]
                dn = {"frugal":"省钱","spend":"愿投","drift":"放弃"}.get(d,d)
                lines.append(f"📊 偏移: {dn}+{o}%")
        except Exception:
            pass
    except Exception:
        pass
    return "\n".join(lines) if lines else ""

def mirror_recent(n=5):
    """魔镜·静 — 最近对话"""
    rows = bs_recent(n)
    if not rows:
        return ""
    items = []
    for ln, ts, txt in rows:
        items.append(f"  {txt[:80]}")
    return "【最近对话】\n" + "\n".join(items)

def mirror_inject():
    """完整注入块 — system_prompt_block替代"""
    parts = [mirror_static()]
    r = mirror_recent(5)
    if r:
        parts.append(r)
    d = mirror_dynamic()
    if d:
        parts.append(d)
    return "\n\n".join(parts)
