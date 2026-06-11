"""NexSandglass L3 — offset_l3"""
import os, re, json, hashlib, logging, math, statistics, shutil
from datetime import datetime, timezone
from sandglass_vault import _tokenize
from sandglass_vault import recent as sv_recent, search as sv_search, count as sv_count
from sandglass_paths import _NB

_VAULT = _NB
_PERSONA_DIR = os.path.join(_VAULT, "persona")
_PERSONA = os.path.join(_PERSONA_DIR, "persona.md")
_PERSONA_TIMELINE = os.path.join(_PERSONA_DIR, "persona-timeline.jsonl")
_DECISION_LOG = os.path.join(_PERSONA_DIR, "decision-log.jsonl")
_TASK_LOG = os.path.join(_PERSONA_DIR, "task-log.jsonl")
_CANVAS = os.path.join(_VAULT, "profile", "canvas.md")
_PATTERNS = os.path.join(_VAULT, "profile", "thinking-patterns.md")
_INSIGHTS = os.path.join(_VAULT, "memory", "insights.md")
logger = logging.getLogger(__name__)

from offset_signals import _OFFSET_SIGNALS

from offset_signals import _LLM_KEY, _LLM_ENDPOINT, _LLM_MODEL

# Lazy imports — avoid circular dependency
_fail_open = None; _llm = None; _extract_md_section = None
_current_stage = None; stage_list = None; scene_current = None; _log_scene_timeline = None; scene_guess = None
_WAVE_THRESHOLDS = None; _weave_guard = None; weave_contradiction = None
def _lazy_import():
    global _fail_open, _llm, _extract_md_section, _current_stage, stage_list, scene_current, _log_scene_timeline, scene_guess, _WAVE_THRESHOLDS, _weave_guard, weave_contradiction
    if _fail_open is None:
        from sandglass_think import _fail_open as _fo, _llm as _l, _extract_md_section as _em
        _fail_open = _fo; _llm = _l; _extract_md_section = _em
    if _current_stage is None:
        from scene_l3 import _log_scene_timeline as _lst, scene_current as _sc, scene_guess as _sg
        from sandglass_think import _current_stage as _cs, stage_list as _sl
        _current_stage = _cs; stage_list = _sl; _log_scene_timeline = _lst
        scene_current = _sc; scene_guess = _sg
    if _WAVE_THRESHOLDS is None:
        from persona_l3 import _WAVE_THRESHOLDS as _wt
        _WAVE_THRESHOLDS = _wt
    if _weave_guard is None:
        from weave_l3 import weave_contradiction as _wc
        _weave_guard = False; weave_contradiction = _wc



_STAGE_THRESHOLD = 60  # ±60% 综合偏移率触发阶段切换信号

_STAGE_CONSECUTIVE = 2  # 连续 2 次高偏移 → 静默切阶段

_FRUGAL = 60   # 省钱信号正在变实（累计+）

_SPEND = -60   # 花钱轮廓正在成形（累计-）

_DRIFT = -80   # 放弃倾向的影子（累计--）

_SEARCH_WEIGHTS = {
    "scene_match": 1.5,     # 当前场景匹配 → ×1.5
    "default": 1.0,          # 默认权重
    "persona_boost": 1.3,   # 画像相关 → ×1.3
    "stage_bias": 0.7,      # 过去阶段 → ×0.7（现在更重要）
    "particle_push": 1.2,   # 决策粒子强化 → ×1.2
}

@__import__("offset_signals")._fail_open({})
def offset_check(decision_text: str, user_persisted: bool = False) -> dict:
    """计算决策偏移率。user_persisted=True 表示主人明知偏移仍坚持。"""
    text = decision_text.lower()

    frugal_hits = sum(1 for w in _OFFSET_SIGNALS["frugal"] if w in text)
    spend_hits = sum(1 for w in _OFFSET_SIGNALS["spend"] if w in text)
    # 🆕 Drift 拆三档独立检测——放弃≠妥协≠烦躁
    drift_giveup = sum(1 for w in _OFFSET_SIGNALS["drift_放弃"] if w in text)
    drift_tradeoff = sum(1 for w in _OFFSET_SIGNALS["drift_妥协"] if w in text)
    drift_irritated = sum(1 for w in _OFFSET_SIGNALS["drift_烦躁"] if w in text)
    drift_hits = drift_giveup + drift_tradeoff + drift_irritated

    # 玻璃——曲面有倒影，不清晰但3D。沙够多，轮廓自然立体
    dimensions = {}
    if drift_hits > 0:
        if drift_giveup > 0:
            offset = -_WAVE_THRESHOLDS["drift"]["放弃"]
            matched = [w for w in _OFFSET_SIGNALS["drift_放弃"] if w in text]
            key = "放弃的影子（深）"
            hints = ["放弃信号浮起来了——" + "、".join(matched[:2]) + "。影子不用怕，留着观察"]
        elif drift_tradeoff > 0:
            offset = -_WAVE_THRESHOLDS["drift"]["妥协"]
            matched = [w for w in _OFFSET_SIGNALS["drift_妥协"] if w in text]
            key = "权衡的影子（中）"
            hints = ["理性权衡——" + "、".join(matched[:2]) + "。不是放弃，是计算"]
        else:
            offset = -_WAVE_THRESHOLDS["drift"]["烦躁"]
            matched = [w for w in _OFFSET_SIGNALS["drift_烦躁"] if w in text]
            key = "烦躁的影子（浅）"
            hints = ["暂时的情绪——" + "、".join(matched[:2]) + "。可能只是累了"]
        direction = "drift"
        dimensions[key] = matched
    elif spend_hits > frugal_hits:
        offset = -(abs(spend_hits - frugal_hits) * 20)
        direction = "spend"
        matched_spend = [w for w in _OFFSET_SIGNALS["spend"] if w in text]
        dimensions["花钱的轮廓"] = matched_spend
        hints = ["愿意投入的轮廓正在成形（" + "、".join(matched_spend[:3]) + "）"]
    elif frugal_hits > 0:
        offset = frugal_hits * 15
        direction = "frugal"
        matched_frugal = [w for w in _OFFSET_SIGNALS["frugal"] if w in text]
        dimensions["省钱的轮廓"] = matched_frugal
        hints = ["省钱的轮廓正在变深（" + "、".join(matched_frugal[:3]) + "）"]
    else:
        offset = 0
        direction = "neutral"
        hints = []

    result = {"offset": offset, "direction": direction, "hints": hints, "dimensions": dimensions}

    # 记录决策
    _log_decision(decision_text, result)

    # 主人明知偏移仍坚持 → 检查是否该切阶段
    if user_persisted and abs(offset) >= _STAGE_THRESHOLD:
        comp = comprehensive_offset()  # ← 先算综合偏移率，再切阶段（切了会清日志）
        new_stage = _maybe_switch_stage(direction)
        if new_stage:
            result["stage_switched"] = True
            result["new_stage"] = new_stage
            result["hints"].append(
                f"🔄 阶段已静默切换：你的决策模式发生了变化，切换前综合偏移率 {comp['offset']:+d}%。新阶段画像将从最近的沙子重新生成。"
            )
        else:
            result["stage_pending"] = True
            result["hints"].append(
                f"📊 当前综合偏移率 {comp['offset']:+d}%。如果再坚持一次同方向，将进入新阶段。"
            )

    return result


def comprehensive_offset(scene: str = "") -> dict:
    """综合偏移率——滚动窗口加权平均。可选按场景过滤。
    scene 参数匹配场景标签列表中的任意一项。"""
    global _weave_guard  # V2.1.10: 修复UnboundLocalError
    _lazy_import()        # V2.1.18: 确保weave_contradiction已加载
    entries = _read_decision_log(50)
    if not entries:
        return {"offset": 0, "direction": "neutral", "sample": 0, "trend": "stable"}

    # 场景过滤
    if scene:
        entries = [e for e in entries if scene in (e.get("scenes") or [])]
        if not entries:
            return {"offset": 0, "direction": "neutral", "sample": 0, "trend": "stable", "scene": scene}

    total = 0
    weight_sum = 0
    directions = {"frugal": 0, "spend": 0, "drift": 0, "neutral": 0}
    chain_stats = {"total_decisions": 0, "hesitations": 0, "avg_chain_len": 0}

    # EMA波浪自吸收——独立于dp_path，对所有entries生效
    EMA_ALPHA = 0.7
    merged = []
    for e in entries:
        if merged and e["direction"] == merged[-1]["direction"] and e["direction"] != "neutral":
            merged[-1]["offset"] = int(merged[-1]["offset"] * EMA_ALPHA + e["offset"] * (1 - EMA_ALPHA))
            merged[-1]["count"] = merged[-1].get("count", 1) + 1
        else:
            merged.append(dict(e, count=1))

    for i, e in enumerate(merged):
        weight = e.get("count", 1)
        total += e["offset"] * weight
        weight_sum += weight
        directions[e["direction"]] += weight

    # 🆕 读取决策粒子链条（仅统计，不影响偏移率计算）
    dp_path = os.path.join(_NB, "decision_particles.txt")
    if os.path.exists(dp_path):
        import re as _re
        with open(dp_path, "r", encoding="utf-8") as f:
            dp_lines = f.readlines()[-100:]
            for line in dp_lines:
                parts = line.strip().split(" | ")
                if len(parts) >= 3:
                    # 格式: ts | options | chain_or_choice | direction | tags
                    chain_or_choice = parts[2]
                    # 检测链条: "A→B→A" 或 "A→B→A 回到A(...)"
                    arrows = _re.findall(r"→\s*(\S+)", chain_or_choice)
                    if len(arrows) >= 2:
                        chain_stats["total_decisions"] += len(arrows)
                        # 回退: 链条中最后一个 = 之前出现过的 → 犹豫
                        if arrows[-1] in arrows[:-1]:
                            chain_stats["hesitations"] += 1
                    elif arrows:
                        chain_stats["total_decisions"] += 1

    avg = round(total / max(weight_sum, 1))

    last5 = [e["offset"] for e in entries[-5:]]
    if len(last5) >= 3:
        recent_avg = sum(last5) / len(last5)
        if recent_avg >= _STAGE_THRESHOLD:
            trend = "shifting_frugal"
        elif recent_avg <= -_STAGE_THRESHOLD:
            trend = "shifting_spend"
        else:
            trend = "stable"
    else:
        trend = "stable"

    result = {
        "offset": avg,
        "direction": max(directions, key=directions.get),
        "sample": len(entries),
        "trend": trend,
        "chain": chain_stats,  # 🆕 决策链条——犹豫度/平均长度
    }
    if scene:
        result["scene"] = scene
    # 偏移超过阈值 → 自动织造（带递归守卫）
    if abs(avg) >= 30 and not _weave_guard:
        try:
            _weave_guard = True
            weave_contradiction()
        except: pass
        finally:
            _weave_guard = False
    return result


@__import__("offset_signals")._fail_open({})
def cross_stage_offset(decision_text: str) -> dict:
    """跨阶段偏移对比——同一个决策放到每个历史阶段的画像上量偏移率。
    返回 {trajectory: [{stage, offset, direction}], evolution: 描述}。
    核心用途：时间回溯——看一个人在多个阶段间的演变轨迹。"""
    _lazy_import()
    result = {"trajectory": [], "evolution": ""}

    # 对每个阶段计算偏移
    stages = stage_list()
    for s in stages:
        persona_path = s.get("persona", "")
        if not os.path.exists(persona_path):
            continue

        with open(persona_path, "r", encoding="utf-8") as f:
            persona_text = f.read().lower()

        # 在当前阶段画像上量同一个决策
        frugal = sum(1 for w in _OFFSET_SIGNALS["frugal"] if w in persona_text)
        spend = sum(1 for w in _OFFSET_SIGNALS["spend"] if w in persona_text)
        drift = sum(1 for w in _OFFSET_SIGNALS["drift_放弃"] if w in persona_text) + \
                sum(1 for w in _OFFSET_SIGNALS["drift_妥协"] if w in persona_text) + \
                sum(1 for w in _OFFSET_SIGNALS["drift_烦躁"] if w in persona_text)

        # 决策本身的方向
        dec_text = decision_text.lower()
        dec_frugal = sum(1 for w in _OFFSET_SIGNALS["frugal"] if w in dec_text)
        dec_spend = sum(1 for w in _OFFSET_SIGNALS["spend"] if w in dec_text)

        # 偏移 = 决策方向 vs 画像基准
        if drift > frugal + spend:
            offset = _DRIFT
            direction = "drift"
        elif spend > frugal:
            offset = (_FRUGAL if dec_spend > dec_frugal else _SPEND)
            direction = "spend"
        elif frugal > 0:
            offset = (_FRUGAL if dec_frugal >= dec_spend else _SPEND)
            direction = "frugal"
        else:
            offset = 0
            direction = "neutral"

        result["trajectory"].append({
            "stage": s["stage"],
            "offset": offset,
            "direction": direction,
            "persona_bias": direction,
        })

    # 生成演变描述
    if len(result["trajectory"]) >= 2:
        first = result["trajectory"][0]
        last = result["trajectory"][-1]
        if first["direction"] != last["direction"]:
            result["evolution"] = (
                f"演变：{first['stage']} 阶段偏向 {first['direction']}，"
                f"{last['stage']} 阶段转向 {last['direction']}。"
                f"跨 {len(result['trajectory'])} 个阶段发生了变化。"
            )
        else:
            result["evolution"] = (
                f"稳定：{first['stage']} 至今，决策倾向始终偏向 {first['direction']}，"
                f"跨 {len(result['trajectory'])} 个阶段保持一致。"
            )

    return result


def offset_guide(query: str) -> dict:
    """搜索前的偏移引导。优先当前画像，降级时间线。"""
    # 优先：当前阶段画像
    if os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8") as f:
            persona_text = f.read()
        bias = "neutral"
        if any(w in persona_text for w in _OFFSET_SIGNALS["frugal"]):
            bias = "frugal"
        elif any(w in persona_text for w in _OFFSET_SIGNALS["spend"]):
            bias = "spend"
        return {"bias": bias, "hints": ["来源：当前阶段画像"]}

    # 降级：时间线
    return {"bias": "neutral", "hints": []}


def offset_chart(topic: str = "") -> str:
    """偏移率 ASCII 可视化。"""
    _lazy_import()
    data = cross_stage_offset(topic) if topic else {"trajectory": []}
    if not data.get("trajectory"):
        comp = comprehensive_offset()
        data = {"trajectory": [{"stage": _current_stage(), "offset": comp["offset"], "direction": comp["direction"]}]}

    lines = ["偏移轨迹"]
    for t in data["trajectory"]:
        off = t.get("offset", 0) or 0
        bar_len = min(abs(off) // 5, 20)
        bar = "█" * bar_len
        sign = "+" if off > 0 else ""
        lines.append(f"  {t['stage']:6s} {sign}{off:3d}% {bar}")
    if data.get("evolution"):
        lines.append(f"  → {data['evolution']}")


    return "\n".join(lines)


def shadow_chart(sensitivity: dict = None) -> str:
    """
    玻璃影子可视化——三个维度的轮廓深度。
    Unicode 阴影条 → 一屏看清省钱/花钱/放弃哪个影子更深。
    """
    if sensitivity is None:
        sensitivity = _WAVE_THRESHOLDS

    comp = comprehensive_offset()
    # 朴素估算三个维度占比（从方向 + 偏移 + 镜像敏感度近似推断）
    frugal_pct = abs(comp["offset"]) if comp["direction"] == "frugal" else max(10, abs(comp["offset"]) // 3)
    spend_pct = abs(comp["offset"]) if comp["direction"] == "spend" else max(10, abs(comp["offset"]) // 4)
    drift_pct = min(50, abs(comp["offset"]) // 5)

    def _bar(pct: int, width: int = 40) -> str:
        filled = pct * width // 100
        return "█" * filled + "░" * (width - filled)

    return "\n".join([
        "🫧 玻璃 — 影子的轮廓",
        f"  省钱 {_bar(frugal_pct)}  {frugal_pct:>3}%（{'深' if frugal_pct > 50 else '浅'}）",
        f"  花钱 {_bar(spend_pct)}  {spend_pct:>3}%（{'深' if spend_pct > 50 else '浅'}）",
        f"  放弃 {_bar(drift_pct)}   {drift_pct:>3}%（{'深' if drift_pct > 30 else '淡'}）",
        f"  {'─' * 40}",
        f"  沙漏 {comp['sample']} 次决策 · 方向: {comp['direction']}",
    ])

_STAGE_MARKS = os.path.join(_PERSONA_DIR, "stage-marks.json")


def _log_decision(decision_text: str, offset_result: dict) -> None:
    """写决策日志。自动附加场景和阶段。"""
    _lazy_import()
    os.makedirs(os.path.dirname(_DECISION_LOG), exist_ok=True)
    scenes = scene_current()
    if not scenes:
        scenes = scene_guess()
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decision": decision_text[:200],
        "offset": offset_result["offset"],
        "direction": offset_result["direction"],
        "stage": _current_stage(),
        "scenes": scenes,
    }
    with open(_DECISION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 同步记录场景时间线
    _log_scene_timeline(scenes)

    # 决策全维度快照（点线面）—— 传offset_result断递归
    try:
        snapshot = decision_snapshot(decision_text, offset_result)
        snap_path = os.path.join(_NB, "decision_snapshots.txt")
        with open(snap_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "decision": decision_text[:200],
                                "snapshot": snapshot}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _read_decision_log(limit: int = 20) -> list:
    """读最近决策日志。"""
    if not os.path.exists(_DECISION_LOG):
        return []
    entries = []
    with open(_DECISION_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return entries[-limit:]


def _maybe_switch_stage(direction: str) -> str | None:
    """检查是否该静默切阶段。返回新阶段名或 None。
    
    触发条件：
    1. 最近20条决策中，同方向≥8条高偏移(≥60%) → 切阶段
    2. 沙子总数跨过500/1000/1500/2000量级 → 自然阶段
    """
    from sandglass_vault import count as sv_count
    
    entries = _read_decision_log(20)
    if len(entries) < 8:
        return None

    # 方式1：累积式——最近20条中同方向高偏移(≥60%)≥8条
    recent = entries[-20:]
    high_offset_same_dir = [e for e in recent 
                           if abs(e["offset"]) >= 60 and e["direction"] == direction]
    
    stage_by_offset = len(high_offset_same_dir) >= 8
    
    # 方式2：沙子量级自然阶段
    total = sv_count()
    stage_by_sand = total % 500 < 10 and total >= 500
    
    if not stage_by_offset and not stage_by_sand:
        return None

    # 阶段名：年月(沙量级) — 如 2026-06(1500)
    now = datetime.now().strftime("%Y-%m")
    stage_name = f"{now}({total // 100 * 100})" if stage_by_sand else f"{now}({total})"
    
    # 归档当前 persona + 生成画布快照
    if os.path.exists(_PERSONA):
        archived = os.path.join(_PERSONA_DIR, f"persona.{stage_name}.md")
        shutil.copy2(_PERSONA, archived)
        persona_canvas(persona_path=archived, stage=stage_name)

    # 记录阶段切换
    os.makedirs(_PERSONA_DIR, exist_ok=True)
    timeline_entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "from_stage": _current_stage(),
        "to_stage": stage_name,
        "direction": direction,
        "trigger": "offset" if stage_by_offset else "sand_milestone",
        "high_offset_count": len(high_offset_same_dir) if stage_by_offset else 0,
        "total_sands": total,
    }
    with open(_PERSONA_TIMELINE, "a", encoding="utf-8") as f:
        f.write(json.dumps(timeline_entry, ensure_ascii=False) + "\n")

    return stage_name


def stage_mark(stage: str, tag: str, note: str = "") -> dict:
    """给阶段打标记。不合并阶段，只标记关联关系。
    例如：stage_mark('2024', 'similar_to', '2025') → 2024 和 2025 相似但不合并"""
    _lazy_import()
    marks = {}
    if os.path.exists(_STAGE_MARKS):
        try:
            with open(_STAGE_MARKS, "r", encoding="utf-8") as f:
                marks = json.loads(f.read())
        except Exception:
            marks = {}

    if stage not in marks:
        marks[stage] = []

    marks[stage].append({
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tag": tag,
        "note": note,
    })

    os.makedirs(os.path.dirname(_STAGE_MARKS), exist_ok=True)
    with open(_STAGE_MARKS, "w", encoding="utf-8") as f:
        json.dump(marks, f, ensure_ascii=False, indent=2)

    return marks


def stage_marks(stage: str = "") -> list:
    """读阶段标记。不指定阶段名则返回所有。"""
    if not os.path.exists(_STAGE_MARKS):
        return []
    try:
        with open(_STAGE_MARKS, "r", encoding="utf-8") as f:
            marks = json.loads(f.read())
        if stage:
            return marks.get(stage, [])
        return marks
    except Exception:
        return []

