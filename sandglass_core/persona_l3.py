"""NexSandglass L3 — persona_l3"""
import os, re, json, hashlib, logging, shutil, time
from datetime import datetime, timezone
from pathlib import Path
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

# Lazy imports — avoid circular dependency
_fail_open = None; _extract_md_section = None
def _lazy_import():
    global _fail_open, _extract_md_section
    if _fail_open is None:
        from sandglass_think import _fail_open as _fo, _extract_md_section as _em
        _fail_open = _fo; _extract_md_section = _em

@__import__("offset_signals")._fail_open("")
def persona_build() -> str:
    """首次全量构建人格画像。从最近500条沙子提炼。返回 persona.md 路径。"""
    _lazy_import()
    from sandglass_vault import recent, count
    from sandglass_think import comprehensive_offset

    total = count()
    limit = min(total, 500)
    sands = recent(limit)
    if not sands:
        return ""

    # 组装沙子供分析
    lines = []
    for ln, ts, text in sands:
        lines.append(f"[L{ln}:{hashlib.sha256(text[:300].encode()).hexdigest()[:8]} | {ts}] {text[:300]}")
    sand_text = "\n".join(lines)

    first_line = sands[-1][0] if sands else 0
    last_line = sands[0][0] if sands else 0

    user_prompt = f"当前时间：{datetime.now():%Y-%m-%d %H:%M}\n沙子范围：L{first_line} ~ L{last_line}\n\n"

    # 玻璃画像 + 影子灵魂 注入
    try:
        glass = glass_reminder("", emotion_trigger=False)
        if glass and "无需提醒" not in glass:
            user_prompt += f"=== 玻璃画像（2D轮廓+3D注解） ===\n{glass}\n\n"
    except Exception: pass
    try:
        off = comprehensive_offset()
        if off.get("direction") and off["direction"] != "neutral":
            proj = persona_project(off["direction"], off.get("offset", 0))
            if proj.get("shadow_persona"):
                user_prompt += f"=== 影子灵魂（如果选相反方向） ===\n{proj['shadow_persona'][:500]}\n\n"
    except Exception: pass

    user_prompt += f"=== 主人对话沙子 ===\n{sand_text[:30000]}\n=== 结束 ===\n\n请执行四层深度扫描，生成 persona.md。首次生成，全量写入。"

    # V2.9.12: 纯本地 → 管道聚合构建（fact_tags + offset + particles + scenes）
    content = _pipe_build(first_line, last_line, total)
    if content:
        os.makedirs(os.path.dirname(_PERSONA), exist_ok=True)
        prev = os.path.join(_PERSONA_DIR, "persona.prev.md")
        if os.path.exists(_PERSONA):
            import shutil
            shutil.copy2(_PERSONA, prev)
        with open(_PERSONA, "w", encoding="utf-8") as f:
            f.write(content)
        return _PERSONA
    return ""


@__import__("offset_signals")._fail_open("")
def persona_update() -> str:
    """增量更新人格画像。只扫描上次更新后的新沙子。"""
    _lazy_import()
    from sandglass_vault import recent, count

    if not os.path.exists(_PERSONA):
        return persona_build()

    with open(_PERSONA, "r", encoding="utf-8") as f:
        existing = f.read()

    # 精确增量扫描：获取上次更新后的新沙子
    since = sand_since_update()
    if since <= 0:
        return _PERSONA
    total_sands = count()
    scan_count = min(since + 20, 500)
    sands = recent(scan_count)
    if not sands:
        return _PERSONA

    # 计算真实行号范围
    first_line = sands[0][0] if sands else 0
    last_line = sands[-1][0] if sands else 0
    sand_count = len(sands)

    lines = []
    for ln, ts, text in sands:
        lines.append(f"[L{ln} | {ts}] {text[:200]}")
    sand_text = "\n".join(lines)

    user_prompt = f"当前时间：{datetime.now():%Y-%m-%d %H:%M}\n\n### 现有画像\n{existing[:4000]}\n\n### 新对话沙子（总{total_sands}条，本条第{first_line}-{last_line}行）\n{sand_text[:15000]}\n\n请增量更新画像。只改有变化的部分，不变的部分原样保留。注意维护项链溯源。"

    # V2.9.9.11: 纯本地 → 数据点驱动更新
    refreshed = _data_driven_refresh(existing, first_line, last_line, total_sands)
    if refreshed:
        with open(_PERSONA, "w", encoding="utf-8") as f:
            f.write(refreshed)
    return _PERSONA


def _data_driven_refresh(existing: str, first_line: int, last_line: int, total: int) -> str:
    """V2.9.9.11: 数据点驱动画像刷新 — 纯本地聚合。
    
    从 fact_tags + offset + decision_particles 提取最新数据点，
    更新画像中的溯源标记、偏移率、标签云等动态字段。
    保留现有画像的结构和定性内容。
    """
    import sqlite3
    from collections import Counter
    from sandglass_think import comprehensive_offset
    
    # 1. fact_tags 高频标签
    tops = []
    try:
        db = sqlite3.connect(os.path.join(_NB, "shadow_sand.db"))
        tags = Counter()
        for r in db.execute("SELECT tags FROM fact_tags WHERE tags != '' AND tags != '未分类'").fetchall():
            for t in r[0].split(","):
                t = t.strip()
                if t and len(t) > 1: tags[t] += 1
        db.close()
        tops = [(t, c) for t, c in tags.most_common(5) if c >= 2]
    except Exception:
        pass
    
    # 2. 偏移率
    off = comprehensive_offset()
    off_dir = off.get("direction", "neutral")
    off_pct = off.get("offset", 0)
    dir_labels = {"frugal": "省钱", "spend": "愿投", "drift": "放弃", "neutral": "平稳"}
    off_label = dir_labels.get(off_dir, "平稳")
    
    # 3. 更新溯源标记
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = existing.split("\n")
    new_lines = []
    header_end = False  # 遇到第一个 ## 标题后为 True
    
    for line in lines:
        # 替换 L 溯源标记
        if line.startswith("<!-- L:"):
            new_lines.append(f"<!-- L: first_line={first_line} last_line={last_line} total={total} -->")
            continue
        # 头部元数据行（image header block）
        if not header_end and line.startswith("> 最后更新"):
            new_lines.append(f"> 最后更新：{now_ts}（数据点驱动 · V2.9.9.11）")
            continue
        if not header_end and "沙子来源" in line:
            new_lines.append(f"> 沙子来源：L{first_line} ~ L{last_line}（共 {total} 条）")
            continue
        if not header_end and "更新方式" in line:
            new_lines.append(f"> 更新方式：fact_tags + decision_particles + offset → 自然累积（纯本地）")
            continue
        
        # 偏移率行（在决策模式区域，用精确匹配）
        if "偏移率" in line and ("省钱" in line or "愿投" in line or "放弃" in line or "平稳" in line):
            new_lines.append(f"  - 偏移率：**{off_label}倾向 {off_pct:+d}%**（{off_dir}，数据点实时）")
            continue
        
        # 标签云行
        if "标签云" in line and "fact_tags" in line:
            tag_str = " · ".join([f"**{t}**" for t, _ in tops]) if tops else "待积累"
            new_lines.append(f"- **标签云**（来自 fact_tags 自动生长）：{tag_str}")
            continue
        
        # 遇到 ## 标题 → 头部结束
        if line.startswith("## "):
            header_end = True
        
        new_lines.append(line)
    
    result = "\n".join(new_lines)
    _sync_five_facets()
    return result


def _pipe_build(first_line: int, last_line: int, total: int) -> str:
    """V2.9.12: 管道聚合首次构建画像 — 纯本地。
    
    从 fact_tags + offset + decision_particles + scenes 生成四层 persona.md。
    新用户空管道 → 输出"待积累"骨架；老用户管道丰富 → 输出完整画像。
    越用管道数据越多，画像越准——自然生长。
    """
    import sqlite3
    from collections import Counter
    from sandglass_think import comprehensive_offset
    
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 1. fact_tags 高频标签 + 工具推断
    tops = []
    tool_hints = []
    try:
        db = sqlite3.connect(os.path.join(_NB, "shadow_sand.db"))
        tags = Counter()
        for r in db.execute("SELECT tags FROM fact_tags WHERE tags != '' AND tags != '未分类'").fetchall():
            for t in r[0].split(","):
                t = t.strip()
                if t and len(t) > 1: tags[t] += 1
        db.close()
        tops = [(t, c) for t, c in tags.most_common(8) if c >= 2]
        # 从标签反推工具
        tool_tags = {"python": "Python", "代码": "Python", "hermes": "Hermes", "沙漏": "沙漏",
                     "sqlite": "SQLite", "github": "GitHub", "微信": "微信", "obsidian": "Obsidian"}
        for t, _ in tops:
            if t.lower() in tool_tags:
                tool_hints.append(tool_tags[t.lower()])
    except Exception:
        pass
    
    # 2. 偏移率
    off = comprehensive_offset()
    off_dir = off.get("direction", "neutral")
    off_pct = off.get("offset", 0)
    
    # 3. 决策粒子最近模式
    dp_chain = ""
    try:
        dp_path = os.path.join(_NB, "decision_particles.txt")
        if os.path.exists(dp_path):
            with open(dp_path, "r", encoding="utf-8", errors="replace") as f:
                dps = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            if dps:
                last = dps[-1]
                if "→" in last:
                    dp_chain = last.split("→")[-1].strip()[:60]
    except Exception:
        pass
    
    # 4. 场景
    scenes_text = ""
    try:
        from scene_l3 import scene_current
        sc = scene_current()
        if sc: scenes_text = "、".join(sc[:3])
    except Exception:
        pass
    
    # ── 组装 persona.md ──
    parts = []
    parts.append(f"<!-- L: first_line={first_line} last_line={last_line} total={total} -->")
    parts.append("# 主人画像 — 管道聚合构建")
    parts.append("")
    parts.append(f"> 首次构建：{now_ts}（管道聚合 · V2.9.12）")
    parts.append(f"> 沙子来源：L{first_line} ~ L{last_line}（共 {total} 条）")
    parts.append(f"> 更新方式：fact_tags + decision_particles + offset → 自然累积")
    parts.append("")
    
    # 🟢 基础锚点
    parts.append("## 🟢 基础锚点")
    if tops:
        top_names = [t for t, _ in tops[:4]]
        parts.append(f"- **标签云**：{' · '.join(top_names)}")
    if tool_hints:
        parts.append(f"- **技术环境**：{', '.join(dict.fromkeys(tool_hints[:5]))}")
    if scenes_text:
        parts.append(f"- **当前场景**：{scenes_text}")
    if off_dir != "neutral":
        dir_cn = {"frugal": "省钱", "spend": "愿投", "drift": "放弃"}
        parts.append(f"- **决策倾向**：{dir_cn.get(off_dir, off_dir)} {off_pct:+d}%")
    if dp_chain:
        parts.append(f"- **最近决策**：{dp_chain}")
    if not tops and not tool_hints:
        parts.append("- 身份：待积累（使用中自动发现）")
    parts.append("")
    
    # 🔵 兴趣图谱
    parts.append("## 🔵 兴趣图谱")
    if tops:
        focus_tags = [t for t, _ in tops[4:]] if len(tops) > 4 else []
        if focus_tags:
            parts.append(f"- **关注方向**：{' · '.join(focus_tags)}")
    if scenes_text:
        parts.append(f"- **活跃场景**：{scenes_text}")
    if not tops:
        parts.append("- 待积累（随着使用自动生长）")
    parts.append("")
    
    # 🟡 交互协议
    parts.append("## 🟡 交互协议")
    parts.append("- **沟通风格**：待积累")
    parts.append("- **雷区/禁区**：待积累")
    parts.append("- **交付偏好**：待积累")
    parts.append("")
    
    # 🔴 认知内核
    parts.append("## 🔴 认知内核")
    if off_dir != "neutral":
        parts.append(f"- **决策模式**：偏移率 {dir_cn.get(off_dir, off_dir)}{off_pct:+d}%")
    if tops:
        parts.append(f"- **价值观信号**：{' · '.join([t for t, _ in tops[:3]])}")
    if dp_chain:
        parts.append(f"- **行为模式**：{dp_chain}")
    if not tops:
        parts.append("- 待积累")
    parts.append("")
    
    # 🔗 项链
    parts.append("## 🔗 项链（关键声明溯源）")
    parts.append(f"- [管道首次构建] → sandglass L{first_line}~L{last_line}")
    
    result = "\n".join(parts)
    _sync_five_facets(first_line, last_line, total)
    return result


def _sync_five_facets(first_line: int = 0, last_line: int = 0, total: int = 0):
    """V2.9.24: 管道自动生成 five-facets.json — 用户零操作。
    从 persona.md + iron_rules.txt + offset + fact_tags 聚合。
    """
    import json
    ff_path = os.path.join(_NB, "profile", "five-facets.json")
    now = datetime.now().strftime("%Y-%m-%d")
    
    ff = {"_schema": "five-facet-profile-v1", "_updated": now, "_source": "pipe-auto"}
    
    # fact: 从 persona.md 提取
    ff["fact"] = []
    if os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8", errors="replace") as f:
            persona_text = f.read()
        for line in persona_text.split("\n"):
            line = line.strip()
            if line.startswith("- **") and "：" in line:
                key, val = line.replace("- **", "").split("：", 1)
                ff["fact"].append({"title": key.strip(), "content": val.strip()[:80],
                                   "importance": 0.8, "confidence": 0.9, "source": "pipe", "updated": now})
    
    # restriction: 从 iron_rules.txt
    ff["restriction"] = []
    ir_path = os.path.join(_NB, "iron_rules.txt")
    if os.path.exists(ir_path):
        with open(ir_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    ff["restriction"].append({"title": line[:30], "content": line,
                                              "importance": 1.0, "confidence": 1.0, "source": "iron_rules", "updated": now})
    
    try:
        os.makedirs(os.path.dirname(ff_path), exist_ok=True)
        with open(ff_path, "w", encoding="utf-8") as f:
            json.dump(ff, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


@__import__("offset_signals")._fail_open("")
def persona_canvas(persona_path: str = "", stage: str = "") -> str:
    """从 persona 生成画布。默认当前阶段。
    指定 persona_path 则从归档画像生成对应阶段画布。"""
    _lazy_import()
    import shutil
    if persona_path and os.path.exists(persona_path):
        with open(persona_path, "r", encoding="utf-8") as f:
            persona_text = f.read()
        stage = stage or Path(persona_path).stem.replace("persona.", "")
    elif os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8") as f:
            persona_text = f.read()
        stage = stage or _current_stage()
    else:
        return ""

    # V2.9.9.9+: 纯本地 — canvas 由 persona_diff + persona_verify 驱动
    return ""


def persona_freshness() -> dict:
    """人格画像过时检测。返回 {stale, since_sands, since_days, warning}"""
    sands = sand_since_update()
    if sands < 0:
        return {"stale": True, "since_sands": -1, "since_days": -1, "warning": "画像不存在"}
    if sands < 30:
        return {"stale": False, "since_sands": sands, "since_days": 0, "warning": ""}
    if sands < 80:
        return {"stale": "mild", "since_sands": sands, "since_days": 0,
                "warning": f"画像已滞后 {sands} 条沙子，建议近期更新"}
    return {"stale": True, "since_sands": sands, "since_days": 0,
            "warning": f"画像已积累 {sands} 条新沙子，轮廓正在生长——可以更新一下"}


def stage_list() -> list:
    """列出所有阶段。返回 [{stage, canvas_path, persona_path, when}]"""
    stages = []
    # 读时间线
    if os.path.exists(_PERSONA_TIMELINE):
        seen = set()
        with open(_PERSONA_TIMELINE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    key = entry["to_stage"]
                    if key not in seen:
                        seen.add(key)
                        stages.append({
                            "stage": key,
                            "canvas": os.path.join(_PERSONA_DIR, f"canvas.{key}.md"),
                            "persona": os.path.join(_PERSONA_DIR, f"persona.{key}.md"),
                            "when": entry["ts"][:10],
                            "from": entry["from_stage"],
                        })
                except Exception:
                    continue

    # 当前阶段
    cur = _current_stage()
    if not any(s["stage"] == cur for s in stages):
        stages.append({
            "stage": cur,
            "canvas": _CANVAS,
            "persona": _PERSONA,
            "when": datetime.now().strftime("%Y-%m-%d"),
            "from": "初始",
        })

    return stages


def stage_canvas(stage: str) -> str | None:
    """读某个阶段的画布内容。快照索引，不是全量画像。"""
    canvas_path = os.path.join(_PERSONA_DIR, f"canvas.{stage}.md")
    if os.path.exists(canvas_path):
        with open(canvas_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    # 降级：当前画布
    if os.path.exists(_CANVAS):
        with open(_CANVAS, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

_SCENE_FILE = os.path.join(_PERSONA_DIR, "scenes.json")

# 场景关键词（可扩展）

def _current_stage() -> str:
    """读当前阶段标签。O(1) — 只读最后一行。"""
    if not os.path.exists(_PERSONA_TIMELINE):
        return "2026-06"
    try:
        with open(_PERSONA_TIMELINE, "rb") as f:
            f.seek(-256, 2)  # 从尾部读最后256字节
            tail = f.read().decode("utf-8", errors="ignore")
        last = tail.strip().split("\n")[-1]
        if not last:
            return "2026-06"
        return json.loads(last)["to_stage"]
    except Exception:
        return "2026-06"


def _load_persona() -> str:
    """加载当前阶段画像文本。缓存避免重复读盘。"""
    if not os.path.exists(_PERSONA):
        return ""
    # 简单实现：不加缓存，保持数据新鲜
    with open(_PERSONA, "r", encoding="utf-8") as f:
        return f.read()


def _local_persona_extract() -> str:
    """本地提取基本画像——纯模式匹配。V1.3。"""
    from sandglass_vault import recent
    from collections import Counter

    sands = recent(500)
    all_text = "\n".join(t[2] for t in sands)

    patterns = {
        "角色": [(r"我是(.+?)(?:[，。！\n]|$)", 12), (r"我做(.+?)(?:[，。！\n]|$)", 12),
                (r"I am (.+?)(?:[.,!?\n]|$)", 12), (r"I work as (.+?)(?:[.,!?\n]|$)", 12)],
        "工具": [(r"(?:用|装|配|跑)(?:了|过)?\s*([A-Za-z][A-Za-z0-9._\-\s]{2,20})", 8),
                 (r"(?:using?|running?|installed?)\s+([A-Za-z][A-Za-z0-9._\-]{2,20})", 8)],
        "偏好": [(r"我(?:喜欢|偏好|习惯|爱)\s*(.{2,30})", 15), (r"我(?:不喜欢|讨厌|烦)\s*(.{2,30})", 15),
                 (r"I (?:like|love|prefer|enjoy)\s+(.{2,60})", 15), (r"I (?:hate|dislike|don't like)\s+(.{2,60})", 15)],
        "决策": [(r"(免费|不花钱|自己搞|省钱|性价比|开源)", 10), (r"(花钱|省事|付费|买|效率优先)", 10),
                 (r"(free|open.source|diy|cheap|cost.effective)", 10), (r"(pay|buy|subscribe|premium)", 10)],
    }

    results = {}
    for cat, rules in patterns.items():
        hits = []
        for pat, _ in rules:
            for m in re.findall(pat, all_text):
                c = m.strip()[:30]
                if c and len(c) >= 2: hits.append(c)
        if hits:
            results[cat] = [w for w, c in Counter(hits).most_common(5) if c >= 2]

    lines = ["# 主人画像 — 本地提取", "", "> 设置API Key后可启用深度扫描。", ""]
    for cat, items in results.items():
        if items:
            lines.append(f"## {cat}")
            for item in items: lines.append(f"- {item}")
            lines.append("")
    # 度量指标收集
    try:
        ml = os.path.join(_NB, "metrics.log")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        from sandglass_vault import count
        total = count()
        metrics = f"[{now}] sands={total} local_extract"
        with open(ml, "a", encoding="utf-8") as f:
            f.write(metrics + "\n")
    except Exception:
        pass

    return "\n".join(lines) if results else "数据不足"

_PERSONA_SYSTEM = """# 🧬 人格架构师 — 渐进演化协议

你是 NeuroBase 的记忆系统。你需要从主人的对话沙子中提炼他的画像，写入 persona.md。

## ⛔ 铁律
1. **只能从提供的对话沙子中提炼，禁止编造。**
2. **每条声明末尾必须附加 `[src:SHA256前8位:L行号]`，直接写在声明行内，不要单独放到底部。**
   例如：`- 职业/角色：口腔诊所老板 [src:a1b2c3d4:L854]`
3. **首次生成用 write 模式全量写，增量更新只改变化部分。**
4. **保持克制：信息不足的维度留空，不要臆测。**
5. **中文输出。**
6. **调用 glass_reminder() 读取当前玻璃画像。调用 persona_project() 读取影子灵魂。**

## 🔬 四层深度扫描

### 🟢 第一层：基础锚点
扫描目标：确凿事实、身份信息、当前状态。

### 🔵 第二层：兴趣图谱  
扫描目标：时间/金钱/注意力投向什么。

### 🟡 第三层：交互协议
扫描目标：沟通习惯、雷区、工作流偏好。

### 🔴 第四层：认知内核
扫描目标：决策逻辑、矛盾点、终极驱动力。

## 📝 输出模板

```markdown
# 主人画像 — 四层深度扫描

> 最后更新：{time}
> 沙子来源：L{first_line} ~ L{last_line}（共 {total} 条）

## 🟢 基础锚点
- 职业/角色：
- 工作地点：
- 技术环境：
- 当前项目/目标：

## 🔵 兴趣图谱
- 技术方向：
- 工具偏好：
- 关注领域：

## 🟡 交互协议（最重要）
- 沟通风格：
- 雷区/禁区：
- 交付偏好：
- 称呼方式：

## 🔴 认知内核
- 决策模式：
- 核心价值观：
- 反复出现的倾向：
- 终极驱动力：

## 🔗 项链（关键声明溯源）
- [声明] → sandglass L行号
```
"""



_CANVAS_SYSTEM = """# 画布生成器

从人格画像生成一张结构化认知地图。输出格式：

```markdown
# 主人认知地图 [{stage}]

> 阶段：{stage}

## 身份
- [一句话]

## 在做的事
- 

## 技术栈
- 

## 决策模式
- 

## 当前焦点
- 

## 禁区/雷区
- 
```

要求：极度精简，每条不超过15字。这是快照索引，不是全量画像。"""


def persona_project(direction: str, offset: int) -> dict:
    """影子灵魂——基于当前偏移方向，模拟「如果选相反方向会变成怎样」。
    读取决策粒子历史，构建反向投影画像，和当前画像对比。
    返回 {shadow_persona, divergence, insight}"""
    dp_path = os.path.join(_NB, "decision_particles.txt")
    if not os.path.exists(dp_path):
        return {"shadow_persona": "", "divergence": 0, "insight": "无决策粒子数据"}

    opposites = {"frugal": "花钱", "spend": "省钱", "drift": "坚持"}
    reverse = opposites.get(direction, "相反方向")
    
    # 回音折——缩小影子选择范围
    wind_direction = 0  # 正=开心/自信，负=焦虑/放弃
    try:
        echo_path = os.path.join(_NB, "echo_wind.jsonl")
        if os.path.exists(echo_path):
            with open(echo_path, "r", encoding="utf-8") as ef:
                for eline in ef:
                    try:
                        rec = json.loads(eline.strip())
                        if rec.get("sentiment") == "正面":
                            wind_direction += rec.get("spread_weight", 1.3)
                        elif rec.get("sentiment") == "负面":
                            wind_direction -= rec.get("spread_weight", 0.8)
                    except Exception: pass
        from sandglass_think import _sentiment_wind
        wind_direction += _sentiment_wind()
    except Exception: pass

    # 读决策粒子——用回音折缩小反向选择范围
    shadow_lines = []
    with open(dp_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(" | ")
            if len(parts) >= 5:
                dir_tag = parts[3]
                emotion_tag = parts[4] if len(parts) > 4 else ""
                # 回音折优先：风正→影子偏向花钱/自信选择，风负→影子偏向省钱/安全选择
                if direction in ("frugal", "spend") and (
                    (direction == "frugal" and any(w in dir_tag.lower() for w in ["spend","花钱","买","付费"])) or
                    (direction == "spend" and any(w in dir_tag.lower() for w in ["frugal","省钱","免费","开源"])) or
                    (direction == "drift" and any(w in dir_tag.lower() for w in ["坚持","继续","不放弃"]))):
                    shadow_lines.append(parts[2][:100])

    if not shadow_lines:
        return {"shadow_persona": "", "divergence": 0,
                "insight": f"影子灵魂: 如果选择{reverse}…数据不足，等待更多交叉决策"}

    # 用织布机追溯影子路径
    try:
        from sandglass_think import weave_graph
        wg = weave_graph(f"{reverse} 方案", max_hops=2)
        causal_hint = wg.get("insight", "") if wg else ""
    except Exception:
        causal_hint = ""

    shadow = f"影子灵魂——如果当初选择{reverse}（偏移{offset:+d}%）:\n"
    shadow += f"  交叉决策: {len(shadow_lines)}条"
    # 回音折信号
    wind_signal = ""
    if wind_direction > 0.5:
        wind_signal = f"  回音折: 正面({wind_direction:+.1f}) → 影子偏向自信路径\n"
    elif wind_direction < -0.5:
        wind_signal = f"  回音折: 负面({wind_direction:+.1f}) → 影子偏向安全路径\n"
    shadow += wind_signal
    for s in shadow_lines[:3]:
        shadow += f"  - {s}\n"
    if causal_hint and "数据不足" not in str(causal_hint):
        shadow += f"  因果追溯: {causal_hint}\n"

    divergence = min(abs(offset) * 2, 100)
    insight = f"影子灵魂: 如果选择{reverse}，偏移差值约{divergence}%。{'差距在拉大——你现在走的这条路正在塑造一个不同的你' if divergence > 50 else '影子还很淡——你和另一个选择差距不大'}"

    # 写入影子灵魂
    shadow_path = os.path.join(_PERSONA_DIR, "persona.shadow.md")
    with open(shadow_path, "w", encoding="utf-8") as f:
        f.write(f"# 影子灵魂 — {reverse}方向\n>\n> 触发偏移: {offset:+d}% ({direction})\n>\n{shadow}")

    # 回音折写回——影子本身产生回音折，影响未来的幽灵决策
    try:
        echo_path = os.path.join(_NB, "echo_wind.jsonl")
        echo_entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sentiment": "正面" if divergence < 40 else "负面",
            "options": f"影子投影:{direction}→{reverse}",
            "spread_weight": round(1.0 + abs(offset) / 200, 2),
            "source": "persona_project"
        }
        os.makedirs(os.path.dirname(echo_path), exist_ok=True)
        with open(echo_path, "a", encoding="utf-8") as ef:
            ef.write(json.dumps(echo_entry, ensure_ascii=False) + "\n")
    except Exception: pass

    return {"shadow_persona": shadow[:500], "divergence": divergence, "insight": insight}


from offset_signals import _OFFSET_SIGNALS

# ── 波浪阈值——单一真相来源。不判对错，只照影子深浅 ──
_WAVE_THRESHOLDS = {
    # 轮廓成形（多少层影子算"成形"）
    "frugal": {"contour": 50},   # 省钱影子叠 50 层 → 轮廓成形
    "spend":  {"contour": 50},   # 同上
    "drift":  {"contour": 30,    # 放弃更敏感
               # 三档权重——同一个"放弃"的不同深浅
               "放弃": 100,       # 深放弃
               "妥协": 60,       # 理性权衡
               "烦躁": 30},      # 暂时情绪
}

# 搜索四维权重——场景匹配/画像增强/阶段偏置/粒子助推
_SEARCH_WEIGHTS = {
    "scene_match": 1.5,     # 当前场景匹配 → ×1.5
    "default": 1.0,          # 默认权重
    "persona_boost": 1.3,   # 画像相关 → ×1.3
    "stage_bias": 0.7,      # 过去阶段 → ×0.7（现在更重要）
    "particle_push": 1.2,   # 决策粒子强化 → ×1.2
}


def sand_since_update() -> int:
    """上次画像更新后新增了多少条沙子。返回 -1 表示画像不存在，999 表示无法解析。"""
    from sandglass_vault import count

    if not os.path.exists(_PERSONA):
        return -1

    with open(_PERSONA, "r", encoding="utf-8") as f:
        head = f.read()[:500]

    # 解析 L 标记：<!-- L: first_line=X last_line=Y total=Z -->
    m = re.search(r"last_line=(\d+)", head)
    if m:
        last_indexed = int(m.group(1))
        total = count()
        return max(0, total - last_indexed)

    # fallback: L 标记解析失败，用文件修改时间估算
    mtime = os.path.getmtime(_PERSONA)
    age_days = (time.time() - mtime) / 86400
    total = count()
    if age_days < 1:
        return max(0, total // 4)  # 最近更新，新沙不多
    elif age_days < 7:
        return max(0, total // 2)
    else:
        return max(1, total)  # 太久没更新，强制触发


def stage_similarity(stage_a: str, stage_b: str) -> dict:
    """比较两个阶段的画像相似度。返回 {overlap, score, suggestion}"""
    def _read_persona(s):
        path = os.path.join(_PERSONA_DIR, f"persona.{s}.md")
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read().lower()

    pa = _read_persona(stage_a)
    pb = _read_persona(stage_b)
    if not pa or not pb:
        return {"overlap": 0, "score": 0, "suggestion": "画像缺失"}

    words_a = set(re.findall(r"[\u4e00-\u9fff]{2,}", pa))
    words_b = set(re.findall(r"[\u4e00-\u9fff]{2,}", pb))
    if not words_a or not words_b:
        return {"overlap": 0, "score": 0, "suggestion": "画像内容不足"}

    overlap = words_a & words_b
    score = len(overlap) / max(len(words_a), len(words_b))

    suggestion = ""
    if score > 0.7:
        suggestion = f"高度相似({score:.0%})，建议标记 similar_to"
    elif score > 0.4:
        suggestion = f"部分相似({score:.0%})"
    else:
        suggestion = f"差异明显({score:.0%})，可能是重要转折点"

    return {"overlap": len(overlap), "score": round(score, 2), "suggestion": suggestion}

