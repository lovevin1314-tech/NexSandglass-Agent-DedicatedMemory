"""
NexSandglass — 第3层：思
=========================
灵魂蒸馏 + 偏移率 + 时间检索 + 织布机
"""

import json
import os
import re
import shutil
import statistics
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

_VAULT = os.path.join(os.path.expanduser("~"), ".neurobase")
_PERSONA_DIR = os.path.join(_VAULT, "persona")
_PERSONA = os.path.join(_PERSONA_DIR, "persona.md")        # 当前阶段画像
_PERSONA_TIMELINE = os.path.join(_PERSONA_DIR, "persona-timeline.jsonl")  # 阶段切换轨迹
_DECISION_LOG = os.path.join(_PERSONA_DIR, "decision-log.jsonl")          # 决策日志
_TASK_LOG = os.path.join(_PERSONA_DIR, "task-log.jsonl")                  # 跨会话待办
_CANVAS = os.path.join(_VAULT, "profile", "canvas.md")
_PATTERNS = os.path.join(_VAULT, "profile", "thinking-patterns.md")
_INSIGHTS = os.path.join(_VAULT, "memory", "insights.md")

# ── LLM 配置 ──
_LLM_KEY = (
    os.environ.get("DEEPSEEK_API_KEY", "")
    or os.environ.get("OPENROUTER_API_KEY", "")
)
_LLM_ENDPOINT = "https://api.deepseek.com/v1/chat/completions" if os.environ.get(
    "DEEPSEEK_API_KEY"
) else "https://openrouter.ai/api/v1/chat/completions"
_LLM_MODEL = (
    "deepseek-chat"
    if os.environ.get("DEEPSEEK_API_KEY")
    else "deepseek/deepseek-v4-flash"
)

# ── fail-open 装饰器 ──
def _fail_open(default):
    """装饰器：任何异常返回 default 值并 log warning。
    用法：@_fail_open([]) 或 @_fail_open({}) 或 @_fail_open(\"\")"""
    def deco(func):
        from functools import wraps
        @wraps(func)
        def wrapper(*a, **kw):
            try:
                return func(*a, **kw)
            except Exception:
                logger.warning("sandglass: %s() failed", func.__name__, exc_info=True)
                return default
        return wrapper
    return deco


def _llm(system: str, user: str, max_tokens: int = 2048) -> str:
    """调 LLM，失败返回空字符串。"""
    if not _LLM_KEY:
        return ""
    payload = json.dumps({
        "model": _LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {_LLM_KEY}",
        "Content-Type": "application/json",
    }
    if "openrouter" in _LLM_ENDPOINT:
        headers["HTTP-Referer"] = "https://neurobase.local"
        headers["X-Title"] = "Sandglass Layer 3"
    try:
        req = urllib.request.Request(_LLM_ENDPOINT, data=payload, headers=headers)
        resp = urllib.request.urlopen(req, timeout=60)
        body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]
    except Exception:
        return ""


# ═══════════════════════════════════════════════
# 人格画像 — 偷师 TencentDB 四层深度扫描
# ═══════════════════════════════════════════════

_PERSONA_SYSTEM = """# 🧬 人格架构师 — 渐进演化协议

你是 NexSandglass 的记忆系统。你需要从主人的对话沙子中提炼他的画像，写入 persona.md。

## ⛔ 铁律
1. **只能从提供的对话沙子中提炼，禁止编造。**
2. **每一条声明如果知道来源行号，注明 `(L行号)`。这叫"项链"——可追溯到 sandglass.txt。**
3. **首次生成用 write 模式全量写，增量更新只改变化部分。**
4. **保持克制：信息不足的维度留空，不要臆测。**
5. **中文输出。**

## 🔬 四层深度扫描

### 🟢 第一层：基础锚点
扫描目标：确凿事实、身份信息、当前状态。
提取：职业角色、工作地点、技术栈、当前项目。

### 🔵 第二层：兴趣图谱  
扫描目标：时间/金钱/注意力投向什么。
提取：活跃爱好、技术偏好、工具选择倾向。

### 🟡 第三层：交互协议
扫描目标：沟通习惯、雷区、工作流偏好。
提取：怎么跟他说话、什么会触怒他、他喜欢怎样交付结果。
**这是最重要的层——教 Agent 如何正确服务主人。**

### 🔴 第四层：认知内核
扫描目标：决策逻辑、矛盾点、终极驱动力。
提取：他做什么决策时反复出现的模式、核心价值观。

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


@_fail_open("")
def persona_build() -> str:
    """首次全量构建人格画像。从最近500条沙子提炼。返回 persona.md 路径。"""
    from sandglass_vault import recent, count

    total = count()
    limit = min(total, 500)
    sands = recent(limit)
    if not sands:
        return ""

    # 组装沙子给 LLM
    lines = []
    for ln, ts, text in sands:
        lines.append(f"[L{ln} | {ts}] {text[:300]}")
    sand_text = "\n".join(lines)

    first_line = sands[-1][0] if sands else 0
    last_line = sands[0][0] if sands else 0

    user_prompt = f"当前时间：{datetime.now():%Y-%m-%d %H:%M}\n沙子范围：L{first_line} ~ L{last_line}\n\n=== 主人对话沙子 ===\n{sand_text[:30000]}\n=== 结束 ===\n\n请执行四层深度扫描，生成 persona.md。首次生成，全量写入。"

    result = _llm(_PERSONA_SYSTEM.format(time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                                          first_line=first_line, last_line=last_line,
                                          total=limit),
                  user_prompt, max_tokens=4096)

    if result:
        os.makedirs(os.path.dirname(_PERSONA), exist_ok=True)
        # 提取 markdown 代码块内容
        m = re.search(r"```(?:markdown)?\s*\n(.*?)```", result, re.DOTALL)
        content = m.group(1).strip() if m else result.strip()
        with open(_PERSONA, "w", encoding="utf-8") as f:
            f.write(content)
        return _PERSONA
    return ""


@_fail_open("")
def persona_update() -> str:
    """增量更新人格画像。只扫描上次更新后的新沙子。"""
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


# ═══════════════════════════════════════════════
# 画布 — 每阶段一张快照索引
# ═══════════════════════════════════════════════

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


@_fail_open("")
def persona_canvas(persona_path: str = "", stage: str = "") -> str:
    """从 persona 生成画布。默认当前阶段。
    指定 persona_path 则从归档画像生成对应阶段画布。"""
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


# ═══════════════════════════════════════════════
# 场景 — 多标签并存，自动检测
# ═══════════════════════════════════════════════

_SCENE_FILE = os.path.join(_VAULT, "persona", "scenes.json")

# 场景关键词（可扩展）
_SCENE_KEYWORDS = {
    "工作项目": ["项目", "任务", "进度", "交付", "上线", "需求", "方案"],
    "学习研究": ["学习", "教程", "算法", "框架", "论文", "原理"],
    "个人事务": ["生活", "日常", "计划", "健身", "旅行", "购物"],
    "技术开发": ["代码", "架构", "部署", "API", "bug", "性能", "脚本"],
}


def _load_scenes() -> list:
    """加载当前场景标签列表。"""
    if not os.path.exists(_SCENE_FILE):
        return []
    try:
        with open(_SCENE_FILE, "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except Exception:
        return []


def _save_scenes(tags: list) -> None:
    """保存场景标签列表。去重。"""
    os.makedirs(os.path.dirname(_SCENE_FILE), exist_ok=True)
    unique = list(dict.fromkeys(tags))  # 保序去重
    with open(_SCENE_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False)


def scene_add(tag: str) -> list:
    """添加一个场景标签。返回当前全部标签。"""
    tags = _load_scenes()
    tag = tag.strip()
    if tag and tag not in tags:
        tags.append(tag)
        _save_scenes(tags)
    return tags


def scene_remove(tag: str) -> list:
    """移除一个场景标签。"""
    tags = _load_scenes()
    tag = tag.strip()
    if tag in tags:
        tags.remove(tag)
        _save_scenes(tags)
    return tags


def scene_current() -> list:
    """返回当前激活的场景标签列表。"""
    return _load_scenes()


def scene_guess() -> list:
    """从最近沙子猜测当前场景标签（可重合多个）。"""
    from sandglass_vault import recent

    sands = recent(15)
    text = " ".join(t[2] for t in sands).lower()

    matched = []
    for scene, keywords in _SCENE_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            matched.append(scene)
    return matched


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


# ═══════════════════════════════════════════════
# 场景时间线 + 沙子增量 + 阶段相似度
# ═══════════════════════════════════════════════

_SCENE_TIMELINE = os.path.join(_PERSONA_DIR, "scene-timeline.jsonl")


def _log_scene_timeline(scenes: list) -> None:
    """记录场景快照。去重：如果和上次完全一样，不记。"""
    os.makedirs(os.path.dirname(_SCENE_TIMELINE), exist_ok=True)
    last_scenes = set()
    if os.path.exists(_SCENE_TIMELINE):
        with open(_SCENE_TIMELINE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                try:
                    last = json.loads(lines[-1].strip())
                    last_scenes = set(last.get("scenes", []))
                except Exception:
                    pass

    cur = set(scenes)
    if cur == last_scenes:
        return

    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": _current_stage(),
        "scenes": sorted(cur),
    }
    with open(_SCENE_TIMELINE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


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


# ═══════════════════════════════════════════════
# 项链 — 声明溯源
# ═══════════════════════════════════════════════

def persona_trace(claim: str) -> list:
    """给定人格声明，搜索 sandglass 找到来源行。返回 [(行号, 时间, 明文), ...]"""
    from sandglass_vault import search

    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", claim)
    query = " ".join(tokens[:5])
    return search(query, limit=5)


# ═══════════════════════════════════════════════
# 偏移率 — 阶段感知 + 综合偏移 + 静默切换
# ═══════════════════════════════════════════════

# 决策关键词（正面/负面信号）
_OFFSET_SIGNALS = {
    "frugal": ["免费", "不花钱", "自己搞", "本地", "省钱", "性价比", "开源"],
    "spend": ["花钱", "省事", "买", "付费", "订阅", "不值", "效率优先"],
    "drift": ["不管了", "能用就行", "不纠结", "随便", "放弃"],
}

# 阶段切换阈值
_STAGE_THRESHOLD = 60  # ±60% 综合偏移率触发阶段切换信号
_STAGE_CONSECUTIVE = 2  # 连续 2 次高偏移 → 静默切阶段

# 偏移值常量
_FRUGAL = 60   # 性价比优先
_SPEND = -60   # 偏向花钱
_DRIFT = -80   # 红牌漂移


def _log_decision(decision_text: str, offset_result: dict) -> None:
    """写决策日志。自动附加场景和阶段。"""
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


@_fail_open({})
def comprehensive_offset(scene: str = "") -> dict:
    """综合偏移率——滚动窗口加权平均。可选按场景过滤。
    scene 参数匹配场景标签列表中的任意一项。"""
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

    for i, e in enumerate(entries):
        weight = i + 1
        total += e["offset"] * weight
        weight_sum += weight
        directions[e["direction"]] += 1

    avg = round(total / weight_sum)

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
    }
    if scene:
        result["scene"] = scene
    return result


def _maybe_switch_stage(direction: str) -> str | None:
    """检查是否该静默切阶段。返回新阶段名或 None。"""
    entries = _read_decision_log(_STAGE_CONSECUTIVE)

    if len(entries) < _STAGE_CONSECUTIVE:
        return None

    # 最近 N 条是否全部同方向高偏移？
    recent = entries[-_STAGE_CONSECUTIVE:]
    if not all(abs(e["offset"]) >= _STAGE_THRESHOLD for e in recent):
        return None
    if not all(e["direction"] == direction for e in recent):
        return None

    # 静默切阶段
    now = datetime.now().strftime("%Y-%m")

    # 归档当前 persona + 生成画布快照
    if os.path.exists(_PERSONA):
        archived = os.path.join(_PERSONA_DIR, f"persona.{now}.md")
        shutil.copy2(_PERSONA, archived)
        # 为刚归档的阶段生成画布快照
        persona_canvas(persona_path=archived, stage=now)

    # 记录阶段切换
    os.makedirs(_PERSONA_DIR, exist_ok=True)
    timeline_entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "from_stage": _current_stage(),
        "to_stage": now,
        "direction": direction,
        "trigger_offset": recent[-1]["offset"],
        "trigger_decision": recent[-1]["decision"],
    }
    with open(_PERSONA_TIMELINE, "a", encoding="utf-8") as f:
        f.write(json.dumps(timeline_entry, ensure_ascii=False) + "\n")

    # 清决策日志——新阶段从零开始
    if os.path.exists(_DECISION_LOG):
        try:
            os.remove(_DECISION_LOG)
        except OSError:
            pass

    return now


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


@_fail_open({})
def offset_check(decision_text: str, user_persisted: bool = False) -> dict:
    """计算决策偏移率。user_persisted=True 表示主人明知偏移仍坚持。"""
    text = decision_text.lower()

    frugal_hits = sum(1 for w in _OFFSET_SIGNALS["frugal"] if w in text)
    spend_hits = sum(1 for w in _OFFSET_SIGNALS["spend"] if w in text)
    drift_hits = sum(1 for w in _OFFSET_SIGNALS["drift"] if w in text)

    # 计算单次偏移率
    if drift_hits > 0:
        offset = _DRIFT
        direction = "drift"
        hints = ["⚠️ 红牌：'不管了/能用就行'信号"]
    elif spend_hits > frugal_hits:
        offset = _SPEND
        direction = "spend"
        hints = ["偏向花钱省事，与性价比优先基准有偏差"]
    elif frugal_hits > 0:
        offset = _FRUGAL
        direction = "frugal"
        hints = ["符合性价比优先基准"]
    else:
        offset = 0
        direction = "neutral"
        hints = []

    result = {"offset": offset, "direction": direction, "hints": hints}

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


@_fail_open({})
def cross_stage_offset(decision_text: str) -> dict:
    """跨阶段偏移对比——同一个决策放到每个历史阶段的画像上量偏移率。
    返回 {trajectory: [{stage, offset, direction}], evolution: 描述}。
    核心用途：时间回溯——看一个人在多个阶段间的演变轨迹。"""
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
        drift = sum(1 for w in _OFFSET_SIGNALS["drift"] if w in persona_text)

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


# ═══════════════════════════════════════════════
# 阶段标记 — 打包关联，不合并
# ═══════════════════════════════════════════════

_STAGE_MARKS = os.path.join(_PERSONA_DIR, "stage-marks.json")


def stage_mark(stage: str, tag: str, note: str = "") -> dict:
    """给阶段打标记。不合并阶段，只标记关联关系。
    例如：stage_mark('2024', 'similar_to', '2025') → 2024 和 2025 相似但不合并"""
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


# ═══════════════════════════════════════════════
# 高级分析 — 人格过时检测、场景转移、稳定性、预测、交叉验证
# ═══════════════════════════════════════════════

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
            "warning": f"⚠️ 画像严重滞后：{sands} 条新沙子未纳入。偏移率可能不准。"}


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
            insight += "。⚠️ 注意力发生了显著转移——核心身份可能已变化。"

    return {"current": latest, "shift": shifts, "insight": insight}


def decision_stability() -> dict:
    """决策稳定性指数。按场景×阶段分析偏移波动。
    返回 {overall: {stability, volatility}, scenes: {scene: {stability}}}"""
    entries = _read_decision_log(100)
    if len(entries) < 5:
        return {"overall": {"stability": "unknown", "volatility": 0}, "scenes": {}}

    # 整体波动
    offsets = [e["offset"] for e in entries]
    volatility = round(statistics.stdev(offsets) if len(offsets) >= 2 else 0)

    if volatility < 15:
        overall = "高度稳定"
    elif volatility < 30:
        overall = "稳定"
    elif volatility < 50:
        overall = "波动"
    else:
        overall = "剧烈波动"

    # 按场景拆分
    scene_data = {}
    for e in entries:
        for sc in (e.get("scenes") or []):
            scene_data.setdefault(sc, []).append(e["offset"])

    scenes = {}
    for sc, vals in scene_data.items():
        if len(vals) >= 2:
            v = round(statistics.stdev(vals))
            if v < 15:
                s = "高度稳定"
            elif v < 30:
                s = "稳定"
            elif v < 50:
                s = "波动"
            else:
                s = "剧烈波动"
            scenes[sc] = {"stability": s, "volatility": v, "samples": len(vals)}

    return {"overall": {"stability": overall, "volatility": volatility}, "scenes": scenes}


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


def scene_stage_cross_validate() -> dict:
    """场景-阶段交叉验证。
    阶段标记说两个阶段相似，但按场景拆分后重新检查——相似只存在于某些场景。
    返回 {findings, suggestion}"""
    marks = stage_marks()
    findings = []

    for stage, tag_list in marks.items():
        for tag_info in tag_list:
            if tag_info.get("tag") == "similar_to":
                similar_stage = tag_info.get("note", "")
                if not similar_stage:
                    continue

                # 对该阶段对做全维度对比
                sim = stage_similarity(stage, similar_stage)

                # 按场景拆分检查：两个阶段的场景历史
                scenes_a = set()
                scenes_b = set()
                for h in scene_history(stage):
                    scenes_a.update(h.get("scenes", []))
                for h in scene_history(similar_stage):
                    scenes_b.update(h.get("scenes", []))

                common = scenes_a & scenes_b
                only_a = scenes_a - scenes_b
                only_b = scenes_b - scenes_a

                finding = {
                    "stage_a": stage, "stage_b": similar_stage,
                    "overall_similarity": sim["score"],
                    "common_scenes": list(common),
                    "unique_to_a": list(only_a),
                    "unique_to_b": list(only_b),
                }

                if only_a or only_b:
                    finding["refined"] = True
                    finding["insight"] = (
                        f"标记 {stage}≈{similar_stage} 需要细化："
                        f"共同场景 {len(common)} 个，"
                        f"{stage} 独有 {list(only_a)}，{similar_stage} 独有 {list(only_b)}。"
                        f"相似只在共同场景内成立。"
                    )
                else:
                    finding["refined"] = False
                    finding["insight"] = f"标记有效：{stage} 和 {similar_stage} 在所有场景上一致"

                findings.append(finding)

    return {"findings": findings, "suggestion": (
        "建议将阶段标记细化到场景粒度：similar_to 只在共同场景内有效"
        if any(f.get("refined") for f in findings)
        else "当前标记在场景维度上一致"
    )}


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
    insight = "；".join(insight_parts) if insight_parts else "所有场景从初始阶段即存在"

    return {"matrix": matrix, "stages": ordered_stages, "scenes": ordered_scenes,
            "first_appear": first_appear, "insight": insight}


# ═══════════════════════════════════════════════
# 跨会话待办 — 织布机：记下"还没做的事"
# ═══════════════════════════════════════════════

def task_defer(task: str, trigger: str = "", note: str = "") -> dict:
    """记下一个延迟任务。trigger = 触发条件描述，如"沙漏系统完成后"。
    返回 {id, task, trigger, status}"""
    os.makedirs(os.path.dirname(_TASK_LOG), exist_ok=True)
    import hashlib
    task_id = hashlib.md5((task + (trigger or "")).encode()).hexdigest()[:8]

    entry = {
        "id": task_id,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task": task,
        "trigger": trigger,
        "note": note,
        "status": "pending",
    }
    with open(_TASK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def task_pending() -> list:
    """列出所有未完成的延迟任务。"""
    if not os.path.exists(_TASK_LOG):
        return []
    tasks = []
    with open(_TASK_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                t = json.loads(line.strip())
                if t.get("status") == "pending":
                    tasks.append(t)
            except Exception:
                continue
    return tasks


def task_done(task_id: str) -> bool:
    """标记任务完成。"""
    if not os.path.exists(_TASK_LOG):
        return False
    lines = []
    found = False
    with open(_TASK_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                t = json.loads(line.strip())
                if t.get("id") == task_id:
                    t["status"] = "done"
                    t["done_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    found = True
                lines.append(json.dumps(t, ensure_ascii=False))
            except Exception:
                lines.append(line.strip())
    if found:
        with open(_TASK_LOG, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return found


def task_check_trigger(keyword: str) -> list:
    """检查是否有任务的触发条件被满足。keyword 匹配 trigger 字段。
    返回匹配到的 pending 任务列表。"""
    pending = task_pending()
    matched = []
    for t in pending:
        trigger = t.get("trigger", "")
        if trigger and keyword.lower() in trigger.lower():
            matched.append(t)
    return matched


def persona_maintain() -> dict:
    """人格自动维护。沙子够了+偏移稳定→自动触发更新。"""
    fresh = persona_freshness()
    if not fresh["since_sands"] or fresh["since_sands"] < 200:
        return {"triggered": False, "reason": "沙子不足（" + str(fresh.get("since_sands", 0)) + "条，需200+）"}

    stab = decision_stability()
    if stab["overall"]["volatility"] >= 50:
        return {"triggered": False, "reason": "决策波动太大（" + str(stab["overall"]["volatility"]) + "），不适合更新画像"}

    result_path = persona_update()
    if result_path:
        persona_canvas()
        return {"triggered": True,
                "reason": "自动维护：" + str(fresh["since_sands"]) + "条新沙子，偏移稳定，画像已更新",
                "result": result_path}
    return {"triggered": False, "reason": "更新失败"}


def novel_scene_detect() -> dict:
    """新场景发现。检测最近沙子中从未在历史阶段出现过的话题。"""
    guessed = set(scene_guess())
    history = scene_history()

    all_historical = set()
    for h in history:
        all_historical.update(h.get("scenes", []))

    novel = guessed - all_historical
    if not novel:
        return {"novel": [], "insight": "无新场景"}

    from sandglass_vault import recent
    sands = recent(20)
    evidence = {}
    for sc in novel:
        keywords = _SCENE_KEYWORDS.get(sc, [])
        for ln, ts, text in sands:
            if any(kw.lower() in text.lower() for kw in keywords):
                evidence[sc] = text[:100]
                break

    return {
        "novel": [{"scene": sc, "evidence": evidence.get(sc, "")} for sc in novel],
        "insight": "发现 " + str(len(novel)) + " 个新场景：" + "、".join(novel) + "。在之前任何阶段都不存在。"
    }


def search_with_stage_label(query: str, limit: int = 5) -> list:
    """搜索并对每条结果标注阶段兼容性。"""
    from sandglass_vault import search as vs

    results = vs(query, limit=limit)
    labeled = []
    for ln, ts, text in results:
        cross = cross_stage_offset(text[:200])
        labeled.append({
            "line": ln, "ts": ts, "text": text[:100],
            "stage_compat": cross["trajectory"],
            "evolution": cross["evolution"],
        })
    return labeled


def search_semantic(query: str, limit: int = 10) -> list:
    """语义搜索——LLM 扩展关键词 + 第二层倒排索引 = 跨语义空间搜索。
    不做向量库，不调 embedding API，不存额外数据。
    返回 [(行号, 时间, 明文, 匹配来源), ...]"""
    from sandglass_vault import search as vs

    # 1. LLM 扩展关键词
    expanded = _llm_expand(query)

    # 2. 用扩展词 + 原词分别搜第二层，合并去重
    seen = set()
    results = []

    for kw in expanded:
        hits = vs(kw, limit=limit * 2)
        for ln, ts, text in hits:
            if ln not in seen:
                seen.add(ln)
                results.append((ln, ts, text, kw))

    # 3. 按行号降序（最新优先），截断
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:limit]


def _llm_expand(query: str) -> list:
    """LLM 语义扩展——把用户查询扩展为多个相关关键词。
    返回 [原词, 扩展词1, 扩展词2, ...]"""
    system = """你是搜索关键词扩展器。用户给你一个查询，你返回一组相关的中文关键词。
规则：
1. 第一个词必须是用户原词
2. 之后返回 3-5 个语义相关的词/短语
3. 只返回关键词，一行一个，不要编号，不要解释
4. 在同义替换之外，也返回上位词和下位词
示例：
输入：怎么保护数据
输出：
怎么保护数据
加密
DPAPI
数据安全
隐私保护
密钥"""

    result = _llm(system, query, max_tokens=200)
    if not result:
        return [query]

    # 解析：取非空行，去重，保留原词
    keywords = []
    for line in result.strip().split("\n"):
        word = line.strip()
        if word and word not in keywords:
            keywords.append(word)
    return keywords if keywords else [query]


def decision_snapshot(decision_text: str) -> dict:
    """决策全维度快照——点、线、面。"""
    point = offset_check(decision_text)
    line = cross_stage_offset(decision_text)

    surface = {}
    for sc in scene_current():
        comp = comprehensive_offset(scene=sc)
        if comp["sample"] > 0:
            surface[sc] = comp

    return {"point": point, "line": line, "surface": surface}


# ═══════════════════════════════════════════════
# 搜索滤镜
# ═══════════════════════════════════════════════

def search_filter(query: str) -> dict:
    """结合偏移率 + 人格画像，返回搜索引导参数。"""
    # 先查偏移
    offset = offset_guide(query)
    # 再读人格画像（如果有的话）
    persona_hints = []
    if os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8") as f:
            persona_text = f.read()
        if "性价比" in persona_text or "省钱" in persona_text:
            persona_hints.append("主人画像：性价比优先型")
        if "追根溯源" in persona_text:
            persona_hints.append("主人画像：追根溯源，不接受'不管了'")
        if "本地" in persona_text:
            persona_hints.append("主人画像：偏好本地方案")

    return {
        "offset": offset,
        "persona": persona_hints,
        "recommendation": (
            "优先搜索免费/开源/本地方案"
            if offset["bias"] == "frugal"
            else "正常搜索"
        ),
    }


# ═══════════════════════════════════════════════
# 织布机 — 第四支柱：前三柱的线织成布
# ═══════════════════════════════════════════════
# 蒸馏的线（你是谁） + 偏移率的线（你怎么变） + 时间检索的线（找什么）
# 织布机不生产新数据，只合成已有数据。


@_fail_open({})
def weave_insight(topic: str) -> dict:
    """织布：给定一个话题，从三个支柱分别取线，织成合成洞察。
    返回 {persona_view, offset_view, search_view, synthesis}"""
    result = {}

    # 蒸馏的线：这个话题在画像里怎么说的
    if os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8") as f:
            persona_text = f.read()
        relevant = []
        for line in persona_text.split("\n"):
            if any(w in line.lower() for w in topic.lower().split()):
                relevant.append(line.strip())
        result["persona_view"] = relevant[:5] if relevant else ["画像中无相关内容"]

    # 偏移率的线：这个话题在决策日志里怎么走的
    from sandglass_vault import search as vs
    sands = vs(topic, limit=5)
    offset_trajectory = cross_stage_offset(topic) if topic else {}
    result["offset_view"] = {
        "trajectory": offset_trajectory.get("trajectory", []),
        "evolution": offset_trajectory.get("evolution", ""),
        "recent_sands": [(ln, ts, txt[:80]) for ln, ts, txt in sands],
    }

    # 时间检索的线：这个话题搜出来的东西
    search = search_with_stage_label(topic, limit=3)
    result["search_view"] = search

    # 织：三条线合成
    synthesis = []
    if result["persona_view"] and result["persona_view"][0] != "画像中无相关内容":
        synthesis.append("画像说：" + result["persona_view"][0][:80])
    if result["offset_view"]["evolution"]:
        synthesis.append("偏移说：" + result["offset_view"]["evolution"])
    if sands:
        synthesis.append("沙子中有 " + str(len(sands)) + " 条相关记录")

    result["synthesis"] = "；".join(synthesis) if synthesis else "数据不足，无法合成"
    return result


@_fail_open({})
def weave_contradiction() -> dict:
    """织布：检测三大支柱之间的自相矛盾。
    返回 [{pillar_a, pillar_b, conflict, evidence}]"""
    conflicts = []

    # 矛盾1：画像说 frugal，偏移率说 spend
    if os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8") as f:
            persona_text = f.read().lower()
        persona_frugal = any(w in persona_text for w in _OFFSET_SIGNALS["frugal"])
        persona_spend = any(w in persona_text for w in _OFFSET_SIGNALS["spend"])

        comp = comprehensive_offset()
        if persona_frugal and comp["direction"] == "spend" and abs(comp["offset"]) >= 30:
            conflicts.append({
                "pillar_a": "蒸馏（画像）", "pillar_b": "偏移率",
                "conflict": "画像说你是省钱派，但最近决策偏向花钱",
                "evidence": "画像词：" + str([w for w in _OFFSET_SIGNALS["frugal"] if w in persona_text][:3]) +
                           "；偏移率：" + str(comp["offset"]) + "% " + comp["direction"],
            })
        elif persona_spend and comp["direction"] == "frugal" and abs(comp["offset"]) >= 30:
            conflicts.append({
                "pillar_a": "蒸馏（画像）", "pillar_b": "偏移率",
                "conflict": "画像说你是花钱派，但最近决策偏向省钱",
                "evidence": "偏移率：" + str(comp["offset"]) + "% " + comp["direction"],
            })

    # 矛盾2：场景占比变了但阶段没切
    dom = scene_dominance()
    if dom.get("shift"):
        for s in dom["shift"]:
            if abs(s["delta"]) >= 30:
                conflicts.append({
                    "pillar_a": "蒸馏（场景）", "pillar_b": "偏移率（阶段）",
                    "conflict": s["scene"] + " 占比从 " + str(s["from_pct"]) + "% 变到 " + str(s["to_pct"]) + "%，但阶段未切换",
                    "evidence": "偏移率趋势：" + comprehensive_offset()["trend"],
                })

    # 矛盾3：稳定性低但无切换预测
    stab = decision_stability()
    pred = stage_switch_prediction()
    if stab["overall"]["volatility"] >= 40 and not pred.get("predicted"):
        conflicts.append({
            "pillar_a": "偏移率（稳定性）", "pillar_b": "偏移率（预测）",
            "conflict": "决策波动" + str(stab["overall"]["volatility"]) + "，但预测说短期不切换",
            "evidence": "波动值高但斜率不足",
        })

    return {"conflicts": conflicts, "suggestion": (
        "需要更新画像以消除认知偏差" if any("画像" in c["pillar_a"] for c in conflicts)
        else "无矛盾" if not conflicts
        else "存在 " + str(len(conflicts)) + " 处跨支柱矛盾，建议审视"
    )}


@_fail_open({})
def weave_chain(start: str, depth: int = 3) -> dict:
    """织布：从一个起点出发，沿着三大支柱往下追，看能牵出什么。
    start 可以是：一个决策、一个画像声明、一个搜索关键词。
    返回 {chain: [{step, pillar, found}], conclusion}"""
    chain = []

    # 第一步：时间检索
    step1 = weave_insight(start)
    chain.append({"step": 1, "pillar": "时间检索", "found": step1.get("search_view", [])})

    if depth < 2:
        return {"chain": chain, "conclusion": "浅度追索完成"}

    # 第二步：偏移率
    cross = cross_stage_offset(start)
    chain.append({"step": 2, "pillar": "偏移率", "found": cross.get("trajectory", [])})

    if depth < 3:
        return {"chain": chain, "conclusion": cross.get("evolution", "无跨阶段变化")}

    # 第三步：蒸馏画像对比
    if os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8") as f:
            persona_text = f.read()
        chain.append({"step": 3, "pillar": "蒸馏（画像）",
                       "found": "画像 " + str(len(persona_text)) + " 字"})

    return {"chain": chain,
            "conclusion": cross.get("evolution", "追索完成") if cross.get("evolution")
            else "该话题在三大支柱中无显著信号"}


# ═══════════════════════════════════════════════
# 蒸馏 — LLM 驱动的结构化提取
# ═══════════════════════════════════════════════

def distill(topic: str = "", save: bool = False) -> str:
    """LLM 蒸馏最近对话。提取关键决策+洞察，写回 vault。"""
    from sandglass_vault import recent

    latest = recent(50)
    if not latest:
        return "(沙漏中没有新对话)"

    lines = []
    for ln, ts, text in latest:
        lines.append(f"[L{ln} | {ts}] {text[:300]}")
    sand_text = "\n".join(lines)

    system = """# 对话蒸馏器

从主人的对话中提取结构化洞察。输出格式：

```markdown
# 每日洞察 — {date}

## 🎯 关键决策
- [决策内容] (L行号)

## 💡 新发现/学习
- [学到了什么]

## ⚠️ 偏移信号
- [如果有偏离基准的决策]
```

要求：
1. 极度精简，每条不超50字
2. 每条注进行号（项链）
3. 没有重要内容就说"今日无重大决策"
4. 中文输出
"""

    user_prompt = f"主题：{topic or '最近对话'}\n\n=== 沙子 ===\n{sand_text[:20000]}\n=== 结束 ==="

    result = _llm(system.format(date=datetime.now().strftime("%Y-%m-%d")),
                  user_prompt, max_tokens=1024)

    if not result:
        # LLM 不可用，降级为简单 dump
        lines = [f"# 每日洞察 — {datetime.now():%Y-%m-%d %H:%M}",
                 f"## 主题: {topic or '最近对话'}",
                 "", "### 最近对话"]
        for ln, ts, text in latest[:10]:
            lines.append(f"- [{ts}] {text[:120]}")
        result = "\n".join(lines)

    summary = result.strip()

    if save:
        os.makedirs(os.path.dirname(_INSIGHTS), exist_ok=True)
        with open(_INSIGHTS, "a", encoding="utf-8") as f:
            f.write(f"\n{summary}\n")

    return summary


# ═══════════════════════════════════════════════
# 会话启动 — 注入画布
# ═══════════════════════════════════════════════

def session_context(n: int = 5) -> str:
    """新会话启动时，返回：场景标签 + 当前阶段画布 + 可选历史阶段。
    降级：最近沙子。"""
    parts = []

    # 1. 场景标签（可多个重合）
    scene = scene_current()
    if not scene:
        scene = scene_guess()
    if scene:
        parts.append(f"## 📍 当前场景：{' · '.join(scene)}")

    # 2. 当前阶段画布（快照索引）
    cur_stage = _current_stage()
    canvas = stage_canvas(cur_stage)
    if canvas:
        parts.append(f"## 🗺 当前阶段画布 [{cur_stage}]")
        parts.append(canvas)

    # 3. 是否有历史阶段可供回溯
    stages = stage_list()
    past = [s for s in stages if s["stage"] != cur_stage]
    if past:
        parts.append(f"## 📜 历史阶段（{len(past)}个）")
        for s in past[-3:]:
            c = stage_canvas(s["stage"])
            if c:
                first_line = c.split("\n")[0] if c else ""
                parts.append(f"- [{s['stage']}] {first_line}")
        parts.append("需要回溯历史阶段时，调 stage_canvas('阶段名') 读快照，或读对应 persona 全量画像。")

    # 3. 待办任务
    pending = task_pending()
    if pending:
        parts.append(f"## 📋 待办（{len(pending)}项）")
        for t in pending[-5:]:
            trig = (" — 触发条件：" + t.get("trigger", "")) if t.get("trigger") else ""
            parts.append("- " + t.get("task", "") + trig)
        parts.append("")

    if parts:
        return "\n\n".join(parts)

    # 降级：最近沙子
    from sandglass_vault import recent
    latest = recent(n)
    if not latest:
        return ""
    lines = ["## 最近对话"]
    for ln, ts, text in latest:
        lines.append(f"- [{ts}] {text[:100]}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════
# 会话启动 — 注入画布+待办
# ═══════════════════════════════════════════════
