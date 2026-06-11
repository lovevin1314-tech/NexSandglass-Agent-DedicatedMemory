"""NexSandglass L3 — persona_l3"""
import os, re, json, hashlib, logging, shutil
from datetime import datetime, timezone
from pathlib import Path
from sandglass_vault import _tokenize, recent as sv_recent, search as sv_search, count as sv_count

_VAULT = os.path.join(os.path.expanduser("~"), ".neurobase")
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
def _lazy_import():
    global _fail_open, _llm, _extract_md_section
    if _fail_open is None:
        from sandglass_think import _fail_open as _fo, _llm as _l, _extract_md_section as _em
        _fail_open = _fo; _llm = _l; _extract_md_section = _em

@__import__("offset_signals")._fail_open("")
def persona_build() -> str:
    """首次全量构建人格画像。从最近500条沙子提炼。返回 persona.md 路径。"""
    _lazy_import()
    from sandglass_vault import recent, count

    total = count()
    limit = min(total, 500)
    sands = recent(limit)
    if not sands:
        return ""

    # 组装沙子给 LLM
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
    except: pass
    try:
        off = comprehensive_offset()
        if off.get("direction") and off["direction"] != "neutral":
            proj = persona_project(off["direction"], off.get("offset", 0))
            if proj.get("shadow_persona"):
                user_prompt += f"=== 影子灵魂（如果选相反方向） ===\n{proj['shadow_persona'][:500]}\n\n"
    except: pass

    user_prompt += f"=== 主人对话沙子 ===\n{sand_text[:30000]}\n=== 结束 ===\n\n请执行四层深度扫描，生成 persona.md。首次生成，全量写入。"

    result = _llm(_PERSONA_SYSTEM.format(time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                                          first_line=first_line, last_line=last_line,
                                          total=limit),
                  user_prompt, max_tokens=4096)

    if result:
        os.makedirs(os.path.dirname(_PERSONA), exist_ok=True)
        m = re.search(r"```(?:markdown)?\s*\n(.*?)```", result, re.DOTALL)
        content = m.group(1).strip() if m else result.strip()
        # 保存旧版本用于diff
        import shutil
        prev = os.path.join(_PERSONA_DIR, "persona.prev.md")
        if os.path.exists(_PERSONA):
            shutil.copy2(_PERSONA, prev)
        with open(_PERSONA, "w", encoding="utf-8") as f:
            f.write(content)
        # 自动画像diff
        try:
            diff = persona_diff()
            logger.info(f"persona_diff: {diff['insight']}")
        except Exception:
            pass
        return _PERSONA

    # LLM 不可用 → 本地关键词提取兜底（V1.3 自生长能力）
    local = _local_persona_extract()
    if local and local != "数据不足":
        os.makedirs(os.path.dirname(_PERSONA), exist_ok=True)
        with open(_PERSONA, "w", encoding="utf-8") as f:
            f.write(local)
        return _PERSONA
    return ""


@__import__("offset_signals")._fail_open("")
def persona_update() -> str:
    """增量更新人格画像。只扫描上次更新后的新沙子。"""
    _lazy_import()
    from sandglass_vault import recent

    if not os.path.exists(_PERSONA):
        return persona_build()

    with open(_PERSONA, "r", encoding="utf-8") as f:
        existing = f.read()

    # 找最近50条沙子
    sands = recent(50)
    if not sands:
        return _PERSONA

    lines = []
    for ln, ts, text in sands:
        lines.append(f"[L{ln} | {ts}] {text[:200]}")
    sand_text = "\n".join(lines)

    user_prompt = f"当前时间：{datetime.now():%Y-%m-%d %H:%M}\n\n### 现有画像\n{existing[:4000]}\n\n### 新对话沙子\n{sand_text[:15000]}\n\n请增量更新画像。只改有变化的部分，不变的部分原样保留。注意维护项链溯源。"

    result = _llm(_PERSONA_SYSTEM.format(time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                                          first_line="?", last_line="?", total="?"),
                  user_prompt, max_tokens=4096)

    if result:
        m = re.search(r"```(?:markdown)?\s*\n(.*?)```", result, re.DOTALL)
        content = m.group(1).strip() if m else result.strip()
        if len(content) > 500:  # 防止空覆盖
            with open(_PERSONA, "w", encoding="utf-8") as f:
                f.write(content)
    return _PERSONA


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

    user_prompt = f"=== 人格画像 ===\n{persona_text[:5000]}\n=== 结束 ===\n请生成认知地图。"

    result = _llm(_CANVAS_SYSTEM.format(stage=stage, time=datetime.now().strftime("%Y-%m-%d %H:%M")),
                  user_prompt, max_tokens=1024)

    if not result:
        return ""

    m = re.search(r"```(?:markdown)?\s*\n(.*?)```", result, re.DOTALL)
    content = m.group(1).strip() if m else result.strip()

    os.makedirs(_CANVAS_DIR, exist_ok=True)
    canvas_path = os.path.join(_CANVAS_DIR, f"canvas.{stage}.md")
    with open(canvas_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 同时更新当前画布（首页快照）
    shutil.copy2(canvas_path, _CANVAS)
    return canvas_path


def persona_freshness() -> dict:
    """人格画像过时检测。返回 {stale, since_sands, since_days, warning}"""
    sands = sand_since_update()
    if sands < 0:
        return {"stale": True, "since_sands": -1, "since_days": -1, "warning": "画像不存在"}
    if sands < 50:
        return {"stale": False, "since_sands": sands, "since_days": 0, "warning": ""}
    if sands < 200:
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
                            "canvas": os.path.join(_CANVAS_DIR, f"canvas.{key}.md"),
                            "persona": os.path.join(_CANVAS_DIR, f"persona.{key}.md"),
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
    canvas_path = os.path.join(_CANVAS_DIR, f"canvas.{stage}.md")
    if os.path.exists(canvas_path):
        with open(canvas_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    # 降级：当前画布
    if os.path.exists(_CANVAS):
        with open(_CANVAS, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None

_SCENE_FILE = os.path.join(_VAULT, "persona", "scenes.json")

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
    """本地提取基本画像——零 LLM，纯模式匹配。V1.3。"""
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
        "关注": [(r"(?:聊|讨论|说|问)(?:了|过)?(.{2,40})", 8),
                 (r"(?:talk|discuss|ask)(?:ed|ing)?\s+(?:about\s+)?(.{2,60})", 8)],
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

    lines = ["# 主人画像 — 本地提取", "", "> 设置API Key后升级为LLM四层深度扫描。", ""]
    for cat, items in results.items():
        if items:
            lines.append(f"## {cat}")
            for item in items: lines.append(f"- {item}")
            lines.append("")
    # 度量指标收集
    try:
        ml = os.path.join(os.path.expanduser("~"), ".neurobase", "metrics.log")
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
2. **每条声明必须注明 `[src:L行号]`——这叫"项链"，可追溯到 sandglass.txt。**
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


_CANVAS_DIR = os.path.join(_VAULT, "persona")

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


def persona_trace(claim: str) -> list:
    """给定人格声明，搜索 sandglass 找到来源行并验证 SHA256 hash。"""
    from sandglass_vault import search

    # 提取 [src:hash:L行号] 格式的溯源标记
    src_match = re.search(r'\[src:([a-f0-9]+):L?(\d+)\]', claim)
    if src_match:
        expected_hash = src_match.group(1)
        line_num = int(src_match.group(2))
        # 验证源行内容是否匹配
        results = search("", limit=1)
        # 直接读沙漏行验证 hash
        sg = os.path.join(os.path.expanduser("~"), ".neurobase", "sandglass.txt")
        if os.path.exists(sg):
            with open(sg, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if i == line_num:
                        actual_hash = hashlib.sha256(line.strip().encode()).hexdigest()[:8]
                        if actual_hash == expected_hash:
                            return [{"line": line_num, "verified": True, "text": line.strip()[:100]}]
                        else:
                            return [{"line": line_num, "verified": False,
                                     "expected": expected_hash, "actual": actual_hash,
                                     "warning": "源行已变或 LLM 幻觉行号"}]
            return [{"line": line_num, "verified": False, "warning": "行号不存在——LLM 幻觉"}]

    # Fallback: no hash tag, do plain search
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", claim)
    query = " ".join(tokens[:5])
    return search(query, limit=5)


def persona_verify() -> dict:
    """一键验证画像所有声明。扫描 [src:hash:L行号] 标签，批量验证 hash。"""
    import hashlib, re
    p = os.path.join(_VAULT, "persona", "persona.md")
    if not os.path.exists(p):
        return {"verified": 0, "failed": 0, "total": 0, "details": [], "insight": "画像不存在"}

    with open(p, "r", encoding="utf-8") as f:
        content = f.read()

    sg = os.path.join(_VAULT, "sandglass.txt")
    if not os.path.exists(sg):
        return {"verified": 0, "failed": 0, "total": 0, "details": [], "insight": "沙漏不存在"}

    # 读沙漏行号索引
    sg_lines = {}
    with open(sg, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            sg_lines[i] = line.strip()

    details = []
    verified = 0
    failed = 0

    for m in re.finditer(r'\[src:([a-f0-9]+):L?(\d+)\]', content):
        expected_hash = m.group(1)
        line_num = int(m.group(2))
        if line_num in sg_lines:
            actual_hash = hashlib.sha256(sg_lines[line_num][:300].encode()).hexdigest()[:8]
            if actual_hash == expected_hash:
                verified += 1
                details.append({"line": line_num, "status": "ok", "hash": expected_hash})
            else:
                failed += 1
                details.append({"line": line_num, "status": "mismatch",
                               "expected": expected_hash, "actual": actual_hash})
        else:
            failed += 1
            details.append({"line": line_num, "status": "missing", "warning": "行号不存在"})

    insight = f"✅ {verified}/{verified+failed} 溯源验证通过" if verified+failed > 0 else "画像中无溯源标签"
    if failed > 0:
        insight += f"，{failed}条异常（{'幻觉行号' if any(d.get('status')=='missing' for d in details) else '源内容已变'}）"
    return {"verified": verified, "failed": failed, "total": verified+failed,
            "details": details, "insight": insight}


def persona_diff() -> dict:
    """对比新旧画像变更——新增/消失/不变的声明。用于persona_update后自动追踪。"""
    import re
    backup = os.path.join(_PERSONA_DIR, "persona.prev.md")
    current = os.path.join(_PERSONA_DIR, "persona.md")

    if not os.path.exists(current):
        return {"added": 0, "removed": 0, "unchanged": 0, "insight": "画像不存在"}
    if not os.path.exists(backup):
        # 首次——保存当前为基准
        import shutil
        shutil.copy2(current, backup)
        return {"added": 0, "removed": 0, "unchanged": 0, "insight": "首次——已保存基线"}

    with open(backup, "r", encoding="utf-8") as f:
        old = f.read()
    with open(current, "r", encoding="utf-8") as f:
        new = f.read()

    # 提取 [src:...] 标签作为声明ID
    def extract_src(text):
        return set(re.findall(r'\[src:([a-f0-9]+):L\d+\]', text))

    old_srcs = extract_src(old)
    new_srcs = extract_src(new)

    added = new_srcs - old_srcs
    removed = old_srcs - new_srcs
    unchanged = old_srcs & new_srcs

    return {"added": len(added), "removed": len(removed), "unchanged": len(unchanged),
            "added_hashes": list(added)[:10], "removed_hashes": list(removed)[:10],
            "insight": f"🆕 {len(added)}新增 💨 {len(removed)}消失 ✅ {len(unchanged)}不变" if added or removed else "无变化"}



def persona_project(direction: str, offset: int) -> dict:
    """影子灵魂——基于当前偏移方向，模拟「如果选相反方向会变成怎样」。
    读取决策粒子历史，构建反向投影画像，和当前画像对比。
    返回 {shadow_persona, divergence, insight}"""
    dp_path = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")
    if not os.path.exists(dp_path):
        return {"shadow_persona": "", "divergence": 0, "insight": "无决策粒子数据"}

    opposites = {"frugal": "花钱", "spend": "省钱", "drift": "坚持"}
    reverse = opposites.get(direction, "相反方向")
    
    # 回音折——缩小影子选择范围
    wind_direction = 0  # 正=开心/自信，负=焦虑/放弃
    try:
        echo_path = os.path.join(os.path.expanduser("~"), ".neurobase", "echo_wind.jsonl")
        if os.path.exists(echo_path):
            with open(echo_path, "r", encoding="utf-8") as ef:
                for eline in ef:
                    try:
                        rec = json.loads(eline.strip())
                        if rec.get("sentiment") == "正面":
                            wind_direction += rec.get("spread_weight", 1.3)
                        elif rec.get("sentiment") == "负面":
                            wind_direction -= rec.get("spread_weight", 0.8)
                    except: pass
        from sandglass_think import _sentiment_wind
        wind_direction += _sentiment_wind()
    except: pass

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
    except:
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
        echo_path = os.path.join(os.path.expanduser("~"), ".neurobase", "echo_wind.jsonl")
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
    except: pass

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
    """上次画像更新后新增了多少条沙子。返回 -1 表示画像不存在。"""
    from sandglass_vault import count

    if not os.path.exists(_PERSONA):
        return -1

    with open(_PERSONA, "r", encoding="utf-8") as f:
        head = f.read()[:500]

    m = re.search(r"L(\d+)", head)
    last_indexed = int(m.group(1)) if m else 0

    total = count()
    return max(0, total - last_indexed)


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

