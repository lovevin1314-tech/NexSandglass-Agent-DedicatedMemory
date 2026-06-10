"""NexSandglass L3 — scene_l3"""
import os, re, json, logging, math, statistics
from datetime import datetime, timezone
from sandglass_vault import _tokenize

_VAULT = os.path.join(os.path.expanduser("~"), ".neurobase")
_PERSONA_DIR = os.path.join(_VAULT, "persona")
_PERSONA = os.path.join(_PERSONA_DIR, "persona.md")
_PERSONA_TIMELINE = os.path.join(_PERSONA_DIR, "persona-timeline.jsonl")
_DECISION_LOG = os.path.join(_PERSONA_DIR, "decision-log.jsonl")
logger = logging.getLogger(__name__)

try: from sandglass_think import _read_decision_log
except: _read_decision_log = lambda n: []

try: from sandglass_think import _fail_open, _llm
except: _fail_open = lambda d: lambda f: f; _llm = None

_SCENE_MODE = None  # None=自动, 'exam'=考试, 'normal'=日常
def scene_mode(mode: str = None) -> str:
    """设置/读取场景模式。'exam'只走影子沙，'normal'全开L3。"""
    global _SCENE_MODE
    if mode: _SCENE_MODE = mode
    if _SCENE_MODE: return _SCENE_MODE
    # 织布机综合判断——情绪熵+偏移率+场景矩阵
    try:
        e = _emotional_entropy()
        off = comprehensive_offset()
        # 高熵+强偏移→情绪波动场景  /  低熵+稳定→考试/分析场景
        if e > 1.0 and abs(off.get('offset',0)) > 40:
            return 'emotional'
        if e < 0.3 and abs(off.get('offset',0)) < 20:
            return 'exam'
        return 'normal'
    except: return 'normal'

from sandglass_vault import _tokenize

_VAULT = os.path.join(os.path.expanduser("~"), ".neurobase")
_PERSONA_DIR = os.path.join(_VAULT, "persona")
_PERSONA = os.path.join(_PERSONA_DIR, "persona.md")        # 当前阶段画像
_PERSONA_TIMELINE = os.path.join(_PERSONA_DIR, "persona-timeline.jsonl")  # 阶段切换轨迹
_DECISION_LOG = os.path.join(_PERSONA_DIR, "decision-log.jsonl")          # 决策日志
_TASK_LOG = os.path.join(_PERSONA_DIR, "task-log.jsonl")                  # 跨会话待办
_CANVAS = os.path.join(_VAULT, "profile", "canvas.md")
_PATTERNS = os.path.join(_VAULT, "profile", "thinking-patterns.md")
_INSIGHTS = os.path.join(_VAULT, "memory", "insights.md")


# ═══════════════════════════════════════════════
# 纪律因子 — L3铁律约束
# ═══════════════════════════════════════════════

from discipline import iron_rules, iron_rules_set

logger = logging.getLogger(__name__)

# ── LLM 配置 ──
_LLM_KEY = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
_deepseek_key = bool(os.environ.get("DEEPSEEK_API_KEY"))
_LLM_ENDPOINT = "https://api.deepseek.com/v1/chat/completions" if _deepseek_key else "https://openrouter.ai/api/v1/chat/completions"
_LLM_MODEL = "deepseek-v4-flash" if _deepseek_key else "deepseek/deepseek-v4-flash"

_SCENE_KEYWORDS = {
    "工作项目": ["项目", "任务", "进度", "交付", "上线", "需求", "方案"],
    "学习研究": ["学习", "教程", "算法", "框架", "论文", "原理"],
    "个人事务": ["生活", "日常", "计划", "健身", "旅行", "购物"],
    "技术开发": ["代码", "架构", "部署", "API", "bug", "性能", "脚本"],
}
def scene_add(tag: str) -> list:
    """添加一个场景标签。返回当前全部标签。"""
    tags = _load_scenes()
    tag = tag.strip()
    if tag and tag not in tags:
        tags.append(tag)
        _save_scenes(tags)
    return tags

def scene_current() -> list:
    """返回当前激活的场景标签列表。"""
    return _load_scenes()

def scene_sync() -> list:
    """同步场景：猜当前 → 合并到已有标签（只增不删）。返回新标签列表。"""
    existing = _load_scenes()
    guessed = scene_guess()
    for tag in guessed:
        if tag not in existing:
            existing.append(tag)
    if existing != _load_scenes():
        _save_scenes(existing)
    return existing

_SCENE_TIMELINE = os.path.join(_PERSONA_DIR, "scene-timeline.jsonl")

def scene_history(stage: str = "") -> list:
    """场景历史。不指定阶段则返回全部。返回 [{ts, stage, scenes}]"""
    if not os.path.exists(_SCENE_TIMELINE):
        return []
    entries = []
    with open(_SCENE_TIMELINE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line.strip())
                if not stage or e.get("stage") == stage:
                    entries.append(e)
            except Exception:
                continue
    return entries

def scene_dominance() -> dict:
    """场景主导权转移分析。
    返回 {current: {scene: %}, shift: [{scene, from_pct, to_pct}], insight: 描述}
    核心：注意力分配变了=你不是同一个人了。"""
    history = scene_history()
    if len(history) < 2:
        return {"current": {}, "shift": [], "insight": "数据不足"}

    # 按阶段分组
    stages = {}
    for h in history:
        s = h.get("stage", "?")
        if s not in stages:
            stages[s] = []
        stages[s].extend(h.get("scenes", []))

    # 每个阶段的场景占比
    stage_pcts = {}
    for stage, scenes in stages.items():
        total = len(scenes)
        if total == 0:
            continue
        counts = {}
        for sc in scenes:
            counts[sc] = counts.get(sc, 0) + 1
        stage_pcts[stage] = {sc: round(c / total * 100) for sc, c in counts.items()}

    # 找最老和最新
    ordered = sorted(stage_pcts.keys())
    if len(ordered) < 2:
        return {"current": stage_pcts.get(ordered[0], {}), "shift": [],
                "insight": "只有一个阶段，无法对比"}

    earliest = stage_pcts[ordered[0]]
    latest = stage_pcts[ordered[-1]]

    # 检测占比变化 >20% 的场景
    all_scenes = set(list(earliest.keys()) + list(latest.keys()))
    shifts = []
    for sc in all_scenes:
        old_pct = earliest.get(sc, 0)
        new_pct = latest.get(sc, 0)
        delta = new_pct - old_pct
        if abs(delta) >= 20:
            shifts.append({"scene": sc, "from_pct": old_pct, "to_pct": new_pct, "delta": delta})

    # 生成洞察
    insight = ""
    if shifts:
        rising = [s for s in shifts if s["delta"] > 0]
        falling = [s for s in shifts if s["delta"] < 0]
        parts = []
        if rising:
            rising_str = "、".join(s["scene"] + "(" + str(s["from_pct"]) + "%→" + str(s["to_pct"]) + "%)" for s in rising)
            parts.append("上升：" + rising_str)
        if falling:
            falling_str = "、".join(s["scene"] + "(" + str(s["from_pct"]) + "%→" + str(s["to_pct"]) + "%)" for s in falling)
            parts.append("下降：" + falling_str)
        if len(ordered) >= 3:
            parts.append(f"跨 {len(ordered)} 个阶段持续变化")
        insight = "；".join(parts)

        if any(abs(s["delta"]) >= 30 for s in shifts):
            insight += "。注意力的影子往新方向移了——核心身份可能在生长"

    return {"current": latest, "shift": shifts, "insight": insight}

def stage_switch_prediction() -> dict:
    """阶段切换预测。基于偏移轨迹斜率估算切换时间。
    返回 {predicted, eta_sands, confidence, trend_slope}"""
    entries = _read_decision_log(50)
    if len(entries) < 10:
        return {"predicted": False, "eta_sands": -1, "confidence": 0, "trend_slope": 0}

    # 简单线性回归：索引 → 偏移值
    n = len(entries)
    xs = list(range(n))
    ys = [e["offset"] for e in entries]

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)

    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0

    # 当前综合偏移
    current = comprehensive_offset()["offset"]
    threshold = _STAGE_THRESHOLD

    if abs(slope) < 0.1:
        return {"predicted": False, "eta_sands": -1, "confidence": 0,
                "trend_slope": round(slope, 2), "insight": "趋势平缓，无切换信号"}

    # 方向
    if slope > 0 and current >= threshold:
        return {"predicted": True, "eta_sands": 0, "confidence": 80,
                "trend_slope": round(slope, 2), "insight": "已在切换中"}

    if slope < 0 and current <= -threshold:
        return {"predicted": True, "eta_sands": 0, "confidence": 80,
                "trend_slope": round(slope, 2), "insight": "已在切换中"}

    # 估算到达阈值所需的步数
    if slope > 0:
        steps_needed = max(0, (threshold - current) / slope)
    else:
        steps_needed = max(0, (-threshold - current) / slope)

    steps_needed = int(steps_needed)
    confidence = min(70, max(10, int(100 - abs(slope) * 20)))

    return {
        "predicted": steps_needed < 30,
        "eta_sands": steps_needed,
        "confidence": confidence,
        "trend_slope": round(slope, 2),
        "insight": f"按当前趋势，约需 {steps_needed} 条决策后到达切换阈值"
        if steps_needed < 30
        else f"按当前趋势，短期内不会切换（还需约 {steps_needed} 条决策）"
    }

def scene_stage_matrix() -> dict:
    """场景-阶段热力图。返回 {matrix: {stage: {scene: count}}, stages, scenes, insight}"""
    history = scene_history()
    if not history:
        return {"matrix": {}, "stages": [], "scenes": [], "insight": "无数据"}

    matrix = {}
    all_scenes = set()
    for h in history:
        stage = h.get("stage", "?")
        if stage not in matrix:
            matrix[stage] = {}
        for sc in h.get("scenes", []):
            matrix[stage][sc] = matrix[stage].get(sc, 0) + 1
            all_scenes.add(sc)

    ordered_stages = sorted(matrix.keys())
    ordered_scenes = sorted(all_scenes)

    first_appear = {}
    for sc in ordered_scenes:
        for stage in ordered_stages:
            if matrix[stage].get(sc, 0) > 0:
                first_appear[sc] = stage
                break

    insight_parts = []
    for sc, stage in first_appear.items():
        if stage != (ordered_stages[0] if ordered_stages else ""):
            insight_parts.append(sc + " 首次出现在 " + stage + " 阶段")

    if len(ordered_stages) == 1:
        # 单阶段：展示场景占比分布，更有信息量
        stage_scenes = matrix[ordered_stages[0]]
        total = sum(stage_scenes.values()) or 1
        dist = [f"{sc} {stage_scenes[sc]/total:.0%}" for sc in ordered_scenes]
        insight = " · ".join(dist)
    elif insight_parts:
        insight = "；".join(insight_parts)
    else:
        insight = "所有场景从初始阶段即存在"

    return {"matrix": matrix, "stages": ordered_stages, "scenes": ordered_scenes,
            "first_appear": first_appear, "insight": insight}

def novel_scene_detect() -> dict:
    """频率突变检测——突增+消退+停用词过滤+偏移率触发。纯统计，零依赖。"""
    import re
    from sandglass_vault import recent
    recent_sands = recent(20)
    hist_sands = recent(200)
    if not recent_sands:
        return {"novel": [], "fading": [], "insight": "数据不足"}

    STOPWORDS = {'什么', '怎么', '这个', '那个', '可以', '就是', '然后', '但是',
                 '因为', '所以', '如果', '虽然', '已经', '还是', '没有', '不是',
                 '一个', '一下', '一些', '有点', '的话', '的时候', '这样', '那样',
                 'the', 'and', 'for', 'this', 'that', 'with', 'from', 'have',
                 'image', 'you', 'llm', 'user', 'time', 'your', 'all', 'are',
                 'not', 'but', 'has', 'was', 'can', 'its', 'get', 'now'}
    # 用户自定义停用词
    sw_file = os.path.join(os.path.expanduser('~'), '.neurobase', 'stopwords.txt')
    if os.path.exists(sw_file):
        with open(sw_file, 'r', encoding='utf-8') as f:
            STOPWORDS.update(w.strip() for w in f.read().split() if w.strip())

    def _words(sands):
        freq = {}
        for _, _, text in sands:
            for w in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}', text.lower()):
                if w not in STOPWORDS:
                    freq[w] = freq.get(w, 0) + 1
        return freq

    recent_freq = _words(recent_sands)
    hist_freq = _words(hist_sands) if hist_sands else {}

    # 突增检测（3倍以上）
    emerging = []
    for w, rc in recent_freq.items():
        hc = hist_freq.get(w, 0)
        if rc >= 2 and (hc == 0 or rc / max(hc, 1) >= 3):
            emerging.append((w, rc, hc))

    # 消退检测（历史高频但现在消失）
    fading = []
    for w, hc in hist_freq.items():
        rc = recent_freq.get(w, 0)
        if hc >= 3 and rc == 0 and w not in STOPWORDS:
            fading.append((w, hc, rc))

    # 偏移率触发器——突增+消退同时存在时自动触发
    drift_trigger = False
    if emerging and fading:
        try:
            comp = comprehensive_offset()
            drift_trigger = abs(comp.get("offset", 0)) >= 30
        except Exception:
            pass

    parts = []
    if emerging:
        top = sorted(emerging, key=lambda x: x[1]/max(x[2],1), reverse=True)[:5]
        parts.append("🆕 " + ", ".join(f"{w}({rc}vs{hc})" for w, rc, hc in top))
    if fading:
        top = sorted(fading, key=lambda x: x[1], reverse=True)[:5]
        parts.append("📉 " + ", ".join(f"{w}(曾{hc}次)" for w, hc, _ in top))
    if drift_trigger:
        parts.append("⚡ 频率突变触发偏移率检查")

    return {"emerging": [{"word": w, "recent": rc, "historical": hc} for w, rc, hc in emerging],
            "fading": [{"word": w, "historical": hc} for w, hc, _ in fading],
            "drift_trigger": drift_trigger,
            "insight": " | ".join(parts) if parts else "无显著变化"}
