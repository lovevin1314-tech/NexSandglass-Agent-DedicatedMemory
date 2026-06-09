"""
NeuroBase Sandglass — 第3层：思
================================
蒸馏 + 偏移率 + 搜索滤镜

核心方法论 — 偷师 TencentDB Agent Memory：
  1. 四层深度扫描 → 人格画像（persona.md）
  2. 画布 → 结构化认知地图（canvas.md）
  3. 项链 → 人格声明可追溯到 sandglass 行号
  4. 渐进更新 → first / incremental 双模式

用法：
  from sandglass_think import persona_build, persona_update, persona_canvas
  from sandglass_think import offset_check, search_filter, distill
"""

import json
import logging
import os
import re
import shutil
import statistics
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

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

logger = logging.getLogger(__name__)

# ── LLM 配置 ──
_LLM_KEY = os.environ.get("DEEPSEEK_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
_deepseek_key = bool(os.environ.get("DEEPSEEK_API_KEY"))
_LLM_ENDPOINT = "https://api.deepseek.com/v1/chat/completions" if _deepseek_key else "https://openrouter.ai/api/v1/chat/completions"
_LLM_MODEL = "deepseek-chat" if _deepseek_key else "deepseek/deepseek-v4-flash"


def _extract_md_section(content, section_name):
    """从 markdown 内容中提取指定 section 的文本。"""
    start_tag = f"## {section_name}"
    start = content.find(start_tag)
    if start < 0:
        return ""
    end = content.find("\n## ", start + len(start_tag))
    if end < 0:
        return content[start:]
    return content[start:end]


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

你是 NeuroBase 的记忆系统。你需要从主人的对话沙子中提炼他的画像，写入 persona.md。

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
        m = re.search(r"```(?:markdown)?\s*\n(.*?)```", result, re.DOTALL)
        content = m.group(1).strip() if m else result.strip()
        with open(_PERSONA, "w", encoding="utf-8") as f:
            f.write(content)
        return _PERSONA

    # LLM 不可用 → 本地关键词提取兜底（V1.3 自生长能力）
    local = _local_persona_extract()
    if local and local != "数据不足":
        os.makedirs(os.path.dirname(_PERSONA), exist_ok=True)
        with open(_PERSONA, "w", encoding="utf-8") as f:
            f.write(local)
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


def _local_persona_extract() -> str:
    """本地提取基本画像——零 LLM，纯模式匹配。V1.3。"""
    from sandglass_vault import recent
    from collections import Counter

    sands = recent(500)
    all_text = "\n".join(t[2] for t in sands)

    patterns = {
        "角色": [(r"我是(.+?)(?:[，。！\n]|$)", 12), (r"我做(.+?)(?:[，。！\n]|$)", 12)],
        "工具": [(r"(?:用|装|配|跑)(?:了|过)?\s*([A-Za-z][A-Za-z0-9._\-\s]{2,20})", 8)],
        "偏好": [(r"我(?:喜欢|偏好|习惯|爱)\s*(.{2,30})", 15), (r"我(?:不喜欢|讨厌|烦)\s*(.{2,30})", 15)],
        "决策": [(r"(免费|不花钱|自己搞|省钱|性价比|开源)", 10), (r"(花钱|省事|付费|买|效率优先)", 10)],
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
    return "\n".join(lines) if results else "数据不足"


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
    # Drift 拆三档——不是一类东西
    "drift_放弃": ["不管了", "放弃", "不搞了"],
    "drift_妥协": ["能用就行", "不纠结", "就那样", "将就"],
    "drift_烦躁": ["随便", "算了", "就这样"],
}

# Drift 三档偏移权重
_DRIFT_WEIGHTS = {
    "drift_放弃": 100,   # 深放弃——最高关注
    "drift_妥协": 60,    # 理性权衡——不是坏事
    "drift_烦躁": 30,    # 暂时情绪——可能只是累了
}

# 阶段切换——小波浪累积触发
_STAGE_THRESHOLD = 60  # ±60% 综合偏移率触发阶段切换信号
_STAGE_CONSECUTIVE = 2  # 连续 2 次高偏移 → 静默切阶段

# 偏移方向常量——不判对错
_FRUGAL = 60   # 省钱信号正在变实（累计+）
_SPEND = -60   # 花钱轮廓正在成形（累计-）
_DRIFT = -80   # 放弃倾向的影子（累计--）

# 镜子敏感度——三层独立，不判对错
_OFFSET_SENSITIVITY = {
    "frugal": 50,   # 省钱影子叠 50 层 → 轮廓成形
    "spend":  50,   # 花钱影子叠 50 层 → 轮廓成形
    "drift":  30,   # 放弃更敏感（30 层就开始注意）
}

# 搜索四维权重——场景匹配/画像增强/阶段偏置/粒子助推
_SEARCH_WEIGHTS = {
    "scene_match": 1.5,     # 当前场景匹配 → ×1.5
    "default": 1.0,          # 默认权重
    "persona_boost": 1.3,   # 画像相关 → ×1.3
    "stage_bias": 0.7,      # 过去阶段 → ×0.7（现在更重要）
    "particle_push": 1.2,   # 决策粒子强化 → ×1.2
}


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
    chain_stats = {"total_decisions": 0, "hesitations": 0, "avg_chain_len": 0}
    # 🆕 读取决策粒子链条
    dp_path = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")
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
        
        chain_len = len([l for l in dp_lines if _re.search(r"→", l)])
        if chain_len:
            chain_stats["avg_chain_len"] = round(chain_stats["total_decisions"] / chain_len, 1)

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
        "chain": chain_stats,  # 🆕 决策链条——犹豫度/平均长度
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
    # 🆕 Drift 拆三档独立检测——放弃≠妥协≠烦躁
    drift_giveup = sum(1 for w in _OFFSET_SIGNALS["drift_放弃"] if w in text)
    drift_tradeoff = sum(1 for w in _OFFSET_SIGNALS["drift_妥协"] if w in text)
    drift_irritated = sum(1 for w in _OFFSET_SIGNALS["drift_烦躁"] if w in text)
    drift_hits = drift_giveup + drift_tradeoff + drift_irritated

    # 玻璃——曲面有倒影，不清晰但3D。沙够多，轮廓自然立体
    dimensions = {}
    if drift_hits > 0:
        # 按最高档取权重
        if drift_giveup > 0:
            offset = _DRIFT_WEIGHTS["drift_放弃"]
            matched = [w for w in _OFFSET_SIGNALS["drift_放弃"] if w in text]
            key = "放弃的影子（深）"
            hints = ["放弃信号浮起来了——" + "、".join(matched[:2]) + "。影子不用怕，留着观察"]
        elif drift_tradeoff > 0:
            offset = _DRIFT_WEIGHTS["drift_妥协"]
            matched = [w for w in _OFFSET_SIGNALS["drift_妥协"] if w in text]
            key = "权衡的影子（中）"
            hints = ["理性权衡——" + "、".join(matched[:2]) + "。不是放弃，是计算"]
        else:
            offset = _DRIFT_WEIGHTS["drift_烦躁"]
            matched = [w for w in _OFFSET_SIGNALS["drift_烦躁"] if w in text]
            key = "烦躁的影子（浅）"
            hints = ["暂时的情绪——" + "、".join(matched[:2]) + "。可能只是累了"]
        direction = "drift"
        dimensions[key] = matched
    elif spend_hits > frugal_hits:
        offset = abs(spend_hits - frugal_hits) * 20
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


def offset_chart(topic: str = "") -> str:
    """偏移轨迹 ASCII 可视化。零依赖，一秒钟看懂你变了多少。"""
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
        sensitivity = _OFFSET_SENSITIVITY

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
            "warning": f"画像已积累 {sands} 条新沙子，轮廓正在生长——可以更新一下"}


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


# 通用技术同义词（模块级常量，避免每次调用 _synonym_expand() 时重建）
_SYNONYMS = {
    "加密": ["DPAPI", "保护", "安全", "隐私", "密钥", "密文"],
    "安全": ["保护", "加密", "隐私", "防护", "DPAPI"],
    "搜索": ["检索", "查询", "查找", "定位", "seek", "find"],
    "记忆": ["存储", "持久化", "memory", "记录", "存档", "回忆"],
    "画像": ["人格", "persona", "profile", "特征", "用户"],
    "偏移": ["变化", "漂移", "shift", "偏移率", "改变", "转向"],
    "索引": ["index", "目录", "倒排", "检索", "关键词"],
    "阶段": ["stage", "时期", "phase", "周期", "时间段"],
    "决策": ["选择", "决定", "判断", "decision", "判断力"],
    "语义": ["含义", "意思", "semantic", "理解", "上下文"],
    "系统": ["框架", "platform", "平台", "架构", "体系"],
    "代理": ["agent", "AI", "助手", "助理", "机器人"],
    "安装": ["部署", "配置", "setup", "install", "搭建"],
    "错误": ["bug", "问题", "异常", "error", "故障", "失败"],
    "优化": ["改进", "提升", "加速", "性能", "效率"],
    "配置": ["设置", "config", "参数", "选项", "环境"],
    "权限": ["保护", "隔离", "sandbox", "限制", "访问"],
    "数据": ["信息", "data", "内容", "记录", "文件"],
    "本地": ["local", "离线", "本地化", "客户端", "本机"],
    "云端": ["cloud", "远程", "在线", "服务器", "SaaS"],
}


def _synonym_expand(query: str) -> list:
    """本地同义词扩展——零 LLM 消耗，覆盖 80% 语义搜索场景。
    返回 [原词, 同义词1, 同义词2, ...]"""
    keywords = [query]
    seen = {query}
    # 2-gram 滑窗分词（和 _tokenize 一致）
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", query))
    for i in range(len(chars) - 1):
        word = chars[i:i + 2]
        for syn in _SYNONYMS.get(word, []):
            if syn not in seen:
                keywords.append(syn)
                seen.add(syn)
    return keywords


def _tfidf_search(query: str, limit: int = 10) -> list:
    """本地 TF-IDF 语义搜索——纯 stdlib，零外部依赖。
    作为语义搜索的第三条 fallback 路径。"""
    import math
    from sandglass_vault import recent, search as vs

    candidates = {}
    for ln, ts, text in recent(200):
        candidates[ln] = text
    for ln, ts, text in vs(query, limit=50):
        candidates[ln] = text
    if not candidates:
        return []

    docs = {ln: _tokenize(text) for ln, text in candidates.items()}
    qt = _tokenize(query)
    N = len(docs)
    df = {}
    for tokens in docs.values():
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}
    q_tf = {}
    for t in qt: q_tf[t] = q_tf.get(t, 0) + 1
    q_vec = {t: (q_tf[t] / max(len(qt), 1)) * idf.get(t, 0) for t in q_tf}

    results = []
    for ln, tokens in docs.items():
        d_tf = {}
        for t in tokens: d_tf[t] = d_tf.get(t, 0) + 1
        d_vec = {t: (d_tf[t] / max(len(tokens), 1)) * idf.get(t, 0) for t in d_tf}
        dot = sum(q_vec.get(t, 0) * d_vec.get(t, 0) for t in set(list(q_vec.keys()) + list(d_vec.keys())))
        q_norm = math.sqrt(sum(v**2 for v in q_vec.values())) or 1
        d_norm = math.sqrt(sum(v**2 for v in d_vec.values())) or 1
        sim = dot / (q_norm * d_norm) if (q_norm * d_norm) > 0 else 0
        if sim > 0.05:
            results.append((ln, candidates[ln][:100], round(sim, 3)))
    results.sort(key=lambda x: x[2], reverse=True)
    return results[:limit]


def _search_with_fallback(expanded, vs, limit=10):
    """用扩展关键词搜索，去重排序。"""
    seen = set()
    results = []
    for kw in expanded[:8]:
        hits = vs(kw, limit=limit * 2)
        for ln, ts, text in hits:
            if ln not in seen:
                seen.add(ln)
                results.append((ln, ts, text, kw))
    if results:
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]
    return []


def search_semantic(query: str, limit: int = 10) -> list:
    """语义搜索——三级降级：LLM扩展 → 同义词 → TF-IDF。零 API Key 也能用。"""
    from sandglass_vault import search as vs

    # 1级：LLM 扩展
    expanded = _llm_expand(query)
    if expanded and len(expanded) > 1:
        results = _search_with_fallback(expanded, vs, limit)
        if results:
            return results

    # 2级：同义词扩展
    expanded = _synonym_expand(query)
    if len(expanded) > 1:
        results = _search_with_fallback(expanded, vs, limit)
        if results:
            return results

    # 3级：TF-IDF 余弦相似度
    tfidf = _tfidf_search(query, limit)
    if tfidf:
        return [(ln, "", text, f"tfidf:{sim}") for ln, text, sim in tfidf]

    return []


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
    """场景+阶段+决策粒子+偏移率 四维感知搜索滤镜。
    返回 {keywords, weights, scene_context, stage_context, decision_bias}"""
    result = {"keywords": [query], "weights": {}, "scene_context": "", "stage_context": "", "decision_bias": ""}

    # ── 场景感知（当前语境）──
    scenes = scene_current()
    if not scenes:
        scenes = scene_guess()
    if scenes:
        result["scene_context"] = f"当前场景：{'、'.join(scenes)}"

    # ── 画像感知（始终生效）──
    if os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8") as f:
            persona = f.read()
        for dim, keywords in [("认知内核", ["决策", "核心价值", "驱动力"]),
                               ("偏好", ["喜欢", "偏好", "开源", "免费", "本地"]),
                               ("工具", ["Python", "Hermes", "DPAPI"])]:
            if any(kw in persona for kw in keywords):
                result["persona_context"] = persona[:500]
                break
    try:
        cross = cross_stage_offset(query)
        if cross.get("evolution"):
            result["stage_context"] = cross["evolution"]
    except Exception:
        pass

    # ── 决策粒子权重注入（主人说的：记忆库学得好→拿着决策粒子和偏移率去强化搜索滤镜）──
    try:
        wf = os.path.join(_VAULT, "search_weights.txt")
        if os.path.exists(wf):
            weights = {}
            with open(wf, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        k, v = line.strip().split(":", 1)
                        weights[k] = int(v)
            # 高权重标签（≥3次）→ 注入搜索偏好
            top = [k for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True)[:5] if v >= 2]
            if top:
                result["decision_weight_boost"] = top
                result["decision_bias"] = f"近期决策倾向：{'、'.join(top)}"
    except Exception:
        pass

    # ── 决策粒子全量喂入 LLM 扩展（让 LLM 吃决策历史推断搜索意图）──
    dp_path = os.path.join(_VAULT, "decision_particles.txt")
    dp_context = ""
    if os.path.exists(dp_path):
        try:
            with open(dp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-15:]
            if lines:
                dp_context = "## 近期决策\n" + "".join(lines)
        except Exception:
            pass

    # ── 时间范围感知 ──
    time_hint = _parse_time_range(query)
    if time_hint:
        result["time_range"] = time_hint

    # ═══════════════════════════════════════════════
    # 注：偏移率（comprehensive_offset）是独立系统，不在此处计算。
    # 搜索滤镜专注：决策粒子权重 → 搜索偏置。偏移率做：计算偏移方向/幅度。
    # ═══════════════════════════════════════════════

    # ── LLM 四维扩展（有 API Key 时）──
    expanded = _llm_expand_with_context(query, 
        result.get("persona_context", ""),
        result.get("scene_context", ""), 
        result.get("stage_context", ""),
        dp_context,
        result.get("decision_bias", ""))
    if expanded and len(expanded) > 1:
        result["keywords"] = expanded
        # 四维权重——场景/画像/阶段/粒子
        base = _SEARCH_WEIGHTS["default"]
        weights = {}
        for kw in expanded:
            w = base
            if any(s in kw for s in (scenes or [])):
                w *= _SEARCH_WEIGHTS["scene_match"]
            if persona_ctx and any(w in kw for w in persona_ctx.split()):
                w *= _SEARCH_WEIGHTS["persona_boost"]
            if result.get("decision_bias"):
                w *= _SEARCH_WEIGHTS["particle_push"]
            weights[kw] = round(w, 2)
        result["weights"] = weights
        result["source"] = "LLM场景+阶段+决策粒子(4D权重)"
    else:
        # 2D 离线也吃决策粒子权重——本地 80 分
        alt_keywords = _synonym_expand(query)
        keywords = alt_keywords if alt_keywords else [query]
        weights = {}
        for kw in keywords:
            w = _SEARCH_WEIGHTS["default"]
            if result.get("decision_weight_boost") and any(t in kw for t in result["decision_weight_boost"]):
                w *= _SEARCH_WEIGHTS["particle_push"]
            weights[kw] = round(w, 2)
        result["keywords"] = keywords
        result["weights"] = weights
        result["source"] = "2D本地权重(决策粒子)"

    # ── 同时保留非LLM路径的关键词作为备选 ──
    result["alt_keywords"] = _synonym_expand(query) if not expanded or len(expanded) <= 1 else []
    if result["alt_keywords"]:
        result["hint"] = f"或者你也可能在找：{'、'.join(result['alt_keywords'][:3])}"

    return result


def _llm_expand_with_context(query: str, persona_ctx: str, scene_ctx: str, stage_ctx: str, dp_ctx: str = "", decision_bias: str = "") -> list:
    """LLM 结合画像+场景+阶段+决策粒子四维上下文扩展关键词。"""
    if not _LLM_KEY:
        return []

    system = """你是搜索关键词扩展器。根据用户的画像、当前场景、历史阶段和近期决策，扩展相关关键词。
规则：
1. 第一个词必须是用户原词
2. 结合画像，返回符合用户偏好的词
3. 结合场景上下文，返回该场景下最可能相关的词
4. 结合阶段轨迹，返回历史上该话题相关的词
5. 结合近期决策倾向，推测用户真正在找什么——决策粒子揭示行为模式，搜索词只是表面意图
6. 返回 3-8 个关键词，一行一个

示例：
画像：性价比优先，偏好开源工具，关注本地加密
场景：NeuroBase开发
阶段轨迹：2024年偏向省钱自研，2025年开始接受付费工具
近期决策：成本观,动手派,独立性
查询：加密
输出：
加密
DPAPI
本地加密
沙漏安全
零依赖
AES"""

    ctx = ""
    if persona_ctx:
        ctx += f"画像：{persona_ctx[:200]}\n"
    if scene_ctx:
        ctx += f"{scene_ctx}\n"
    if stage_ctx:
        ctx += f"阶段轨迹：{stage_ctx}\n"
    if decision_bias:
        ctx += f"{decision_bias}\n"
    if dp_ctx:
        ctx += f"{dp_ctx}\n"

    user = f"{ctx}查询：{query}"
    result = _llm(system, user, max_tokens=200)

    if not result:
        return []

    keywords = []
    for line in result.strip().split("\n"):
        word = line.strip()
        if word and word not in keywords:
            keywords.append(word)
    return keywords if keywords else []


def _parse_time_range(query: str) -> list:
    """解析模糊时间表达式，返回年份列表。有LLM更准，无LLM关键词匹配。"""
    now_year = datetime.now().year

    # LLM模式
    if _LLM_KEY:
        result = _llm(
            "你是时间解析器。返回JSON数组年份。'两三年前'→[2024,2023]，'去年'→[2025]，无时间→[]。只返回JSON。",
            query, max_tokens=100
        )
        if result:
            try:
                m = re.search(r'\[[\d,\s]+\]', result)
                if m:
                    years = json.loads(m.group())
                    if years:
                        return [str(y) for y in range(min(years)-1, max(years)+2)]
            except Exception:
                pass

    # 无LLM：关键词
    patterns = [
        (r"(两三|[一二三]?四?)年前", lambda m: [now_year-4, now_year-1]),
        (r"大概(.+?)年前", lambda m: [now_year-int(m.group(1))-1, now_year-int(m.group(1))+1]),
        (r"去年", lambda m: [now_year-1]),
        (r"前年", lambda m: [now_year-2]),
        (r"最近(.+?)年", lambda m: list(range(now_year-int(m.group(1)), now_year+1))),
    ]
    for pat, fn in patterns:
        m = re.search(pat, query)
        if m:
            return [str(y) for y in fn(m)]
    return []


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
    result["persona_view"] = ["画像不存在"]
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

    # 矛盾4：3D 立体注解 vs 2D 偏移 —— 玻璃穿了，但看到的和记录的不一致
    three_d = _latest_annotation()
    if three_d and three_d.get("persona_type"):
        comp = comprehensive_offset()
        # 3D 说"成本敏感型"但最近在花 → 矛盾
        if "成本" in three_d.get("persona_type", "") and comp["direction"] == "spend" and abs(comp["offset"]) >= 30:
            conflicts.append({
                "pillar_a": "3D 玻璃", "pillar_b": "2D 偏移",
                "conflict": "3D 立体像说他是成本敏感型，但最近决策全部偏向花钱",
                "evidence": f"3D: {three_d['persona_type']} | 偏移: {comp['offset']:+d}% {comp['direction']}",
            })
        # 3D 说"压力期"但画像没有放弃信号 → 内在矛盾
        if "压力" in three_d.get("emotional_state", "") and comp["direction"] != "drift":
            conflicts.append({
                "pillar_a": "3D 玻璃", "pillar_b": "2D 偏移",
                "conflict": "3D 感知到压力，但决策没出现放弃信号——可能在硬撑",
                "evidence": f"3D: {three_d['emotional_state']} | 偏移: {comp['direction']}",
            })
        # 3D 提醒语气变了 → 画像偏移不一致
        if three_d.get("reminder_tone") and three_d.get("prev_tone"):
            if three_d["reminder_tone"] != three_d["prev_tone"]:
                conflicts.append({
                    "pillar_a": "3D 玻璃", "pillar_b": "3D 玻璃（上一阶段）",
                    "conflict": f"提醒语气从「{three_d['prev_tone']}」变成了「{three_d['reminder_tone']}」——他变了",
                    "evidence": f"当前阶段：{three_d.get('persona_type','?')}",
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


def weave_links() -> dict:
    """互链层——跨阶段关联自动发现并喂给当前画像。
    过去封存不动，变化规律长进现在的你。"""
    stages = stage_list()
    if len(stages) < 2:
        return {"linked": False, "insight": "需要至少2个阶段才能生成互链"}

    links = []
    for i in range(len(stages) - 1):
        a, b = stages[i]["stage"], stages[i + 1]["stage"]
        sim = stage_similarity(a, b)
        cross = cross_stage_offset(b)
        links.append({
            "from": a, "to": b,
            "similarity": sim["score"],
            "trajectory": cross.get("trajectory", []),
        })

    # 全部吸收——小波浪自然累积成大波浪
    if links:
        first = links[0]
        last = links[-1]

        total_drift = 0
        for lk in links:
            for t in lk.get("trajectory", []):
                total_drift += abs(t.get("offset", 0))

        sim_trend = "上升" if last["similarity"] > first["similarity"] else "下降"
        summary = "波动如常——小波浪在累积" if total_drift < 30 * len(links) else f"累积偏移 {total_drift}%——影子已经很深了，轮廓快成形了"
        insight = (
            f"跨 {len(stages)} 个阶段，画像相似度{sim_trend}"
            f"（{first['similarity']:.0%}→{last['similarity']:.0%}）。{summary}。"
        )

        # 追加到当前画像
        if os.path.exists(_PERSONA):
            with open(_PERSONA, "r", encoding="utf-8") as f:
                persona = f.read()

            # 统计互链层已有笔记数（匹配日期格式的笔记行）
            links_section = persona.split("## 🔗 互链层")[-1] if "## 🔗 互链层" in persona else ""
            note_count = len(re.findall(r"^- \[\d{4}-\d{2}-\d{2}\]", links_section))

            with open(_PERSONA, "a", encoding="utf-8") as f:
                f.write(f"\n- [{datetime.now():%Y-%m-%d}] {insight}\n")

            # 累积 ≥5条 或 总偏移 ≥60% → 触发画像重整
            if note_count >= 5 or total_drift >= 60:
                persona_update()
                return {"linked": True, "links": links, "insight": insight,
                        "consolidated": True, "reason": f"累积{note_count+1}条笔记/偏移{total_drift}%——已重整画像"}

        return {"linked": True, "links": links, "insight": insight}

    return {"linked": False, "insight": "无跨阶段变化"}


# ═══════════════════════════════════════════════
# 镜子决策 — 织布机照见主人的过去
# ═══════════════════════════════════════════════

def mirror_decision(question: str) -> dict:
    """
    织布机新入口——主人面临选择，镜子照见过去的影子。
    
    流程：
    ① 拆问题为关键词 → 搜沙子 → 找匹配的决策粒子
    ② 搜历史决策模式 → 类似选择时主人怎么做的
    ③ 读当前偏移率 → 影子现在往哪边倒
    ④ 输出：过去的数据，不给结论
    
    返回 {past_decisions, similar_queries, current_trend, persona_hint}
    """
    from sandglass_vault import search, count as sv_count

    result = {
        "question": question,
        "past_decisions": [],
        "similar_queries": [],
        "current_trend": "",
        "persona_hint": "",
    }

    # ① 搜历史沙子
    similar = search(question[:30], limit=10)
    if similar:
        result["similar_queries"] = [
            f"[{ts[:10]}] {text[:80]}..." for _, ts, text in similar[:5]
        ]

    # ② 搜决策粒子
    dp_path = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")
    if os.path.exists(dp_path):
        try:
            with open(dp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # 关键词匹配
            keywords = set(question.lower().split())
            matches = []
            for line in lines[-100:]:
                if any(kw in line.lower() for kw in keywords if len(kw) > 1):
                    parts = line.strip().split(" | ")
                    if len(parts) >= 4:
                        matches.append({
                            "ts": parts[0][:10],
                            "options": parts[1] if len(parts) > 1 else "",
                            "choice": parts[2] if len(parts) > 2 else "",
                            "direction": parts[3] if len(parts) > 3 else "",
                            "tags": parts[4] if len(parts) > 4 else "",
                        })
            if matches:
                result["past_decisions"] = matches[-5:]
        except Exception:
            pass

    # ③ 当前偏移趋势
    try:
        comp = comprehensive_offset()
        if comp["sample"] >= 2:
            direction_cn = {"frugal": "省钱", "spend": "愿意投入", "drift": "放弃倾向"}
            d = direction_cn.get(comp["direction"], comp["direction"])
            result["current_trend"] = f"影子偏向{d}（{comp['offset']:+d}%），{comp['sample']}次决策"
    except Exception:
        pass

    # ④ 画像提示（有 LLM 时总结）
    if _LLM_KEY and result["past_decisions"]:
        try:
            persona_text = ""
            if os.path.exists(_PERSONA):
                with open(_PERSONA, "r", encoding="utf-8") as f:
                    persona_text = f.read()[:1500]

            past_summary = "\n".join(
                f"- {d['ts']}: {d['options']} → {d['choice']} ({d['direction']})"
                for d in result["past_decisions"]
            )

            system = (
                "你是决策镜子。你有用户画像 + 他过去面对类似选择时的历史。"
                "不要说'应该选什么'——只总结他过去的模式和行为倾向。"
                "一句话，15字以内。"
            )

            llm_result = _llm(
                system,
                f"问题：{question}\n画像：{persona_text}\n趋势：{result['current_trend']}\n\n过去类似决策：\n{past_summary}",
                max_tokens=60,
            )
            if llm_result:
                result["persona_hint"] = llm_result.strip()[:50]
        except Exception:
            pass

    return result


def stage_brief() -> str:
    """
    织布机——阶段简报。阶段切换时生成更新日志。
    不自动推送，主人手动调用。
    
    格式：阶段名、触发原因、偏移率、高权重标签、关键决策
    """
    from sandglass_vault import count as sv_count
    
    lines = []
    total = sv_count()

    # 阶段信息
    try:
        sw = stage_switch_prediction()
        lines.append(f"🧬 阶段简报 — {datetime.now():%Y-%m-%d}")
        lines.append("─" * 40)
        if sw.get("current_stage"):
            lines.append(f"当前阶段: {sw['current_stage']}")
        if sw.get("predicted") and sw.get("next_stage"):
            lines.append(f"预切换: {sw['current_stage']} → {sw['next_stage']}")
            lines.append(f"原因: {sw.get('reason', '连续偏移超阈值')}")
    except Exception:
        lines.append(f"🧬 阶段简报 — {datetime.now():%Y-%m-%d}")

    # 偏移率
    try:
        comp = comprehensive_offset()
        if comp["sample"] >= 2:
            direction_cn = {"frugal": "省钱", "spend": "愿意投入", "drift": "放弃倾向"}
            d = direction_cn.get(comp["direction"], comp["direction"])
            lines.append(f"\n📊 偏移率: {comp['offset']:+d}%（{d}），{comp['sample']}次决策")
    except Exception:
        pass

    # 高权重标签
    try:
        wf = os.path.join(os.path.expanduser("~"), ".neurobase", "search_weights.txt")
        if os.path.exists(wf):
            with open(wf, "r", encoding="utf-8") as f:
                top = [line.strip() for line in f.readlines()[:5] if line.strip()]
            if top:
                lines.append(f"\n🔑 高权重标签: {', '.join(top)}")
    except Exception:
        pass

    # 最近 3 条决策
    try:
        dp_path = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")
        if os.path.exists(dp_path):
            with open(dp_path, "r", encoding="utf-8") as f:
                recent = f.readlines()[-3:]
            if recent:
                lines.append(f"\n📝 最近决策:")
                for r in recent:
                    parts = r.strip().split(" | ")
                    if len(parts) >= 4:
                        lines.append(f"  {parts[0][:10]} {parts[1][:30]} → {parts[2][:30]} ({parts[3]})")
    except Exception:
        pass

    lines.append(f"\n沙漏: {total}条")
    return "\n".join(lines)


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
- [如果影子往某个方向移动了，写下方向+幅度]

## 偏移的轮廓
- [省钱/花钱/放弃的轮廓——哪个正在变深]
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
# 3D 玻璃——阶段注解（永久，不扔）
# ═══════════════════════════════════════════════
# 2D 离线 = 玻璃曲面，沙自然累积 → 轮廓渐清（小标签）
# 3D 在线 = LLM 吃进所有 2D 影子 → 合成立体像（大标签，永久保存）
# 每个阶段可以有多个注解——阶段切了、偏移变了、沙子够了、情绪波动了 → 重新生成


_3D_ANNOTATIONS = os.path.join(os.path.expanduser("~"), ".neurobase", "3d_annotations.jsonl")

# ── 3D 解锁门槛：本地优先，2000 条沙子 + LLM → 才启用立体合成 ──
_THREE_D_UNLOCK = 2000

def _three_d_ready() -> bool:
    """3D 是否已解锁。本地累积够 + LLM 可用。"""
    if not _LLM_KEY:
        return False
    try:
        from sandglass_vault import count
        return count() >= _THREE_D_UNLOCK
    except Exception:
        return False


def _should_synthesize() -> tuple[bool, str]:
    """
    判断是否该生成新的 3D 注解。四个触发条件：
    ① 阶段切换 → 新阶段该有新的大标签
    ② 偏移率超 ±60% → 轮廓变了
    ③ 沙子里程碑（比上次生成多 100 条）→ 够多了重新看
    ④ 情绪波动（焦虑/放弃/开心）→ 立刻重新审视
    
    返回 (should, trigger_reason)
    """
    try:
        from sandglass_vault import count as sv_count
        current = sv_count()
    except Exception:
        return False, ""

    # 没有注解 → 首次生成
    if not os.path.exists(_3D_ANNOTATIONS):
        return True, "first_synthesis"

    # 读最后一条注解
    last_line = ""
    with open(_3D_ANNOTATIONS, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last_line = line.strip()
    if not last_line:
        return True, "corrupted_annotations"

    try:
        last = json.loads(last_line)
    except Exception:
        return True, "parse_error"

    # ① 阶段切换
    current_stage_name = ""
    try:
        log = _read_decision_log(1)
        if log:
            current_stage_name = log[-1].get("stage", "")
    except Exception:
        pass
    if current_stage_name and current_stage_name != last.get("stage", ""):
        return True, f"stage_switch:{last.get('stage','?')}→{current_stage_name}"

    # ② 偏移率超阈值
    try:
        comp = comprehensive_offset()
        if abs(comp["offset"]) >= _STAGE_THRESHOLD:
            return True, f"offset_threshold:{comp['offset']:+.0f}%"
    except Exception:
        pass

    # ③ 沙子 +100
    last_count = last.get("sand_count", 0)
    if current >= last_count + 100:
        return True, f"sand_milestone:{last_count}→{current}"

    # ④ 情绪波动 — 由 pulse.py 调用时传入
    # （这里只是信号检查，实际情绪由 emotion_vocab.detect 决定）
    return False, ""


def _save_annotation(data: dict, trigger: str) -> None:
    """保存阶段注解——永久追加，不替换旧注解。"""
    try:
        current_stage = "?"
        from sandglass_vault import count as sv_count
        try:
            log = _read_decision_log(1)
            if log:
                current_stage = log[-1].get("stage", "?")
        except Exception:
            pass

        annotation = {
            "stage": current_stage,
            "generated_at": datetime.now().isoformat(),
            "trigger": trigger,
            "sand_count": sv_count(),
            "persona_type": data.get("persona_type", ""),
            "emotional_state": data.get("emotional_state", ""),
            "decision_pattern": data.get("decision_pattern", ""),
            "reminder_tone": data.get("reminder_tone", ""),
            "reminder_example": data.get("reminder_example", ""),
            "offset_direction": data.get("offset", {}).get("direction", ""),
            "offset_value": data.get("offset", {}).get("offset", 0),
        }
        os.makedirs(os.path.dirname(_3D_ANNOTATIONS), exist_ok=True)
        with open(_3D_ANNOTATIONS, "a", encoding="utf-8") as f:
            f.write(json.dumps(annotation, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _latest_annotation() -> dict:
    """读最新一条阶段注解。无注解返回空 dict。"""
    if not os.path.exists(_3D_ANNOTATIONS):
        return {}
    last_line = ""
    with open(_3D_ANNOTATIONS, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last_line = line.strip()
    try:
        return json.loads(last_line)
    except Exception:
        return {}


def _synthesize_3d(force: bool = False, trigger: str = "") -> dict:
    """
    3D 立体画像合成——永久注解模式。
    
    - 先检查 _should_synthesize() → 不需要生成则返回最新注解
    - 需要生成 → LLM 吃全量数据 → 保存为永久注解
    - 不接 LLM 返回空 dict → 上游走 2D 玻璃
    """
    if not _LLM_KEY:
        return {}

    # 检查是否该生成（除非强制或情绪波动触发）
    if not force and trigger not in ("emotion_spike",):
        should, reason = _should_synthesize()
        if not should:
            return _latest_annotation()

    try:
        # 1. 画像
        persona_text = ""
        if os.path.exists(_PERSONA):
            with open(_PERSONA, "r", encoding="utf-8") as f:
                persona_text = f.read()[:3000]

        # 2. 偏移率 + 粒子
        comp = comprehensive_offset()
        particles = _read_decision_log(20)
        particle_text = "\n".join(
            f"{e['ts'][:10]} | {e['direction']:6s} | {e.get('tags','')}"
            for e in particles[-20:]
        ) if particles else "无决策粒子"

        # 3. 织布机矛盾
        weave_text = ""
        weave_path = os.path.join(os.path.expanduser("~"), ".neurobase", "weave_alerts.txt")
        if os.path.exists(weave_path):
            with open(weave_path, "r", encoding="utf-8") as f:
                weave_text = f.read()[-500:]

        # 4. 搜索权重
        weight_text = ""
        wf = os.path.join(os.path.expanduser("~"), ".neurobase", "search_weights.txt")
        if os.path.exists(wf):
            with open(wf, "r", encoding="utf-8") as f:
                weight_text = f.read()[:500]

        system = (
            "你是深层人格分析师。你拥有用户的完整画像、决策历史、偏移趋势、"
            "织布机矛盾检测和搜索权重。基于这些数据，回答四个问题：\n\n"
            "1. 这是什么类型的人？（一句话，20字以内）\n"
            "2. 他最近的情绪状态？（一句话）\n"
            "3. 他的决策模式特征？（平时怎样，什么情况下会变）\n"
            "4. 对这种人，什么样的提醒语气最有效？"
            "（小二式热情/好奇式提问/分享式观察/数据式汇报/安静不打扰）\n"
            "5. 给一个具体的提醒例句（30字以内，体现你最推荐的那个语气）\n\n"
            "输出 JSON 格式：\n"
            '{"persona_type":"","emotional_state":"","decision_pattern":"","reminder_tone":"","reminder_example":""}\n\n'
            "不要用「你」称呼用户，用「他」。只输出 JSON。"
        )

        user_prompt = (
            f"## 画像\n{persona_text}\n\n"
            f"## 偏移率\n方向：{comp['direction']}  幅度：{comp['offset']}%  "
            f"样本：{comp['sample']}条  趋势：{comp.get('trend','?')}\n\n"
            f"## 决策粒子（最近20条）\n{particle_text}\n\n"
            f"## 织布机矛盾\n{weave_text or '无矛盾'}\n\n"
            f"## 搜索权重（热门话题）\n{weight_text or '无数据'}"
        )

        result = _llm(system, user_prompt, max_tokens=300)
        if not result:
            return {}

        m = re.search(r"\{.*\}", result, re.DOTALL)
        if m:
            data = json.loads(m.group())
            data["source"] = "3D 玻璃合成"
            data["timestamp"] = datetime.now().isoformat()
            data["offset"] = comp
            data["depth"] = {
                "frugal": comp.get("frugal_pct", comp["offset"] if comp["direction"] == "frugal" else 0),
                "spend": comp.get("spend_pct", abs(comp["offset"]) if comp["direction"] == "spend" else 0),
                "drift": comp.get("drift_pct", 100 if comp["direction"] == "drift" else 0),
            }

            # 永久保存注解
            _save_annotation(data, trigger if trigger else "periodic")

            return data

        return {"raw": result, "source": "3D 玻璃合成（非JSON）"}

    except Exception:
        return {}


def glass_reminder(user_message: str = "", emotion_trigger: bool = False) -> str:
    """
    玻璃提醒——阶段注解 + 2D 兜底。

    - 先读最新 3D 阶段注解 → 直接用（永久保存的）
    - 触发条件满足 → 重新合成 3D
    - 无 LLM → 2D 描述方向

    不判对错，不说"该怎样"。
    """
    trigger = ""
    if emotion_trigger:
        trigger = "emotion_spike"

    # ── 3D 路径：沙漏 ≥ 2000 条 + 有 LLM → 启用立体合成 ──
    syn = {}
    if _three_d_ready():
        # 读最新注解或触发 3D 合成
        syn = _latest_annotation()
        if not syn or emotion_trigger:
            should, reason = _should_synthesize()
            if should or emotion_trigger:
                syn = _synthesize_3d(force=bool(emotion_trigger), trigger=trigger)

    if syn and "reminder_example" in syn:
        direction_cn = {"frugal": "省钱", "spend": "愿意投入", "drift": "放弃倾向"}
        d = syn.get("offset_direction", "")
        contour = f"影子偏向{direction_cn.get(d, d)}（{syn.get('offset_value',0):+d}%）"
        if syn.get("persona_type"):
            contour += f"，{syn['persona_type']}"

        annotation_hint = ""
        if os.path.exists(_3D_ANNOTATIONS):
            count = sum(1 for _ in open(_3D_ANNOTATIONS, "r", encoding="utf-8"))
            if count > 1:
                annotation_hint = f"（共 {count} 个阶段注解）"

        return "\n".join([
            f"🫧 玻璃：{contour} {annotation_hint}",
            f"> {syn['reminder_example']}",
        ])

    # 回退 2D 玻璃
    try:
        from sandglass_vault import count
        total = count()
        if total < 5:
            return ""
        comp = comprehensive_offset()
        if comp["sample"] < 2:
            return ""
        direction_cn = {"frugal": "省钱", "spend": "愿意投入", "drift": "放弃倾向", "neutral": ""}
        d = direction_cn.get(comp["direction"], "")
        if not d:
            return ""
        sensitivity = _OFFSET_SENSITIVITY.get(comp["direction"], 50)
        if comp["sample"] >= sensitivity:
            desc = f"最近{comp['sample']}条决策里——{d}的影子叠了{comp['sample']}层，轮廓已经成形了"
        else:
            desc = f"最近{comp['sample']}条决策里——{d}的影子正在叠加（{comp['sample']}/{sensitivity}）"
        return f"🫧 玻璃：{desc}"
    except Exception:
        return ""


# ═══════════════════════════════════════════════
# 情绪熵 — V1.4 精神回归：香农熵量化情绪波动
# ═══════════════════════════════════════════════

def _emotional_entropy(recent_n: int = 10) -> float:
    """
    香农熵——量化情绪波动程度。
    0 = 完全平静（全是同一种情绪）
    ~1.95 = 高熵（7种情绪均匀分布，波动大）
    """
    import math
    from emotion_vocab import detect as emotion_detect
    from sandglass_vault import recent

    sands = recent(recent_n + 5)  # 多取几条，过滤空
    if not sands:
        return 0.0

    # 收集最近消息的情绪标签
    mood_counts = {}
    total = 0
    for _, _, text in sands[-recent_n:]:
        if not text: continue
        det = emotion_detect(text)
        if det.get("mood"):
            mood_counts[det["mood"]] = mood_counts.get(det["mood"], 0) + 1
            total += 1

    if total == 0:
        return 0.0

    # H = -Σ p_i × log(p_i)
    entropy = 0.0
    for count in mood_counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log(p)
    return round(entropy, 2)


def entropy_reminder(user_message: str = "") -> str:
    """
    熵提醒——情绪熵驱动提醒语气。
    高熵 → 陪伴式安静提醒     低熵 → 小二热情提醒
    """
    entropy = _emotional_entropy()

    if entropy > 1.2:
        tone = "安静的陪伴"
        msg = "情绪波动比较大，我安静陪着。需要的时候叫我。"
    elif entropy < 0.5:
        tone = "小二热情"
        msg = "状态很稳！有事尽管说。"
    else:
        tone = "平稳关注"
        msg = "一切如常。有需要叫我。"

    return f"🫧 熵 {entropy}（{tone}）\n> {msg}"


def entropy_chart(recent_n: int = 10) -> str:
    """
    情绪熵 ASCII 可视化。
    """
    entropy = _emotional_entropy(recent_n)
    bar_len = min(int(entropy * 20), 40)
    bar = "█" * bar_len + "░" * (40 - bar_len)
    level = "高熵波动" if entropy > 1.2 else ("低熵平静" if entropy < 0.5 else "中熵平稳")
    return f"🫧 情绪熵 {entropy:.2f} {bar}  {level}"


# ═══════════════════════════════════════════════
# 会话启动 — 注入画布+待办
# ═══════════════════════════════════════════════

# ═══════════════════════════════════════════════
# MCP 记忆包 — 一键迁移全部记忆数据
# ═══════════════════════════════════════════════

def memory_migrate(output_path: str = "") -> str:
    """
    一键导出全部记忆数据为 tar.gz。换电脑时解压到新 .neurobase/ 即可。
    
    打包内容：
      sandglass.txt / sandglass.backup（沙子+阴影）
      sandglass.idx（米粒索引）
      persona/（画像+阶段+时间线）
      decision_particles.txt（决策粒子）
      search_weights.txt / echo_wind.jsonl（搜索权重+回音折风）
    
    不打包代码——只打包记忆本身。
    """
    import tarfile, os
    
    if not output_path:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = os.path.join(desktop, f"neurobase_memory_{ts}.tar.gz")
    
    # 要打包的文件和目录
    to_pack = [
        "sandglass.txt",
        "sandglass.backup",
        "sandglass.idx",
        "decision_particles.txt",
        "decision_particles_backup.txt",
        "search_weights.txt",
        "echo_wind.jsonl",
    ]
    
    # 目录整体打包（保持结构）
    dirs_to_pack = [
        "persona",
        "chatlog",
    ]
    
    with tarfile.open(output_path, "w:gz") as tar:
        for f in to_pack:
            fp = os.path.join(_VAULT, f)
            if os.path.exists(fp):
                tar.add(fp, arcname=f)
        
        for d in dirs_to_pack:
            dp = os.path.join(_VAULT, d)
            if os.path.exists(dp):
                tar.add(dp, arcname=d)
    
    size_kb = os.path.getsize(output_path) / 1024
    return f"✅ 记忆包已导出：{output_path}（{size_kb:.0f} KB）\n   解压到新电脑的 ~/.neurobase/ 即可恢复全部记忆。"
