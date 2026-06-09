"""
NexSandglass 决策粒子 — 第三层通用燃料 V2
==========================================
三层标签架构：
  ① 本地关键词（baseline，免费快）
  ② LLM 深层推断（enhance，喂画像+阶段+粒子+织布机，自己推，不抄表面理由）
  ③ _learn()  自进化（LLM 出新标签 → 学进本地词库 → 下次免费命中）
==========================================
"""

import os, json
from datetime import datetime

_PARTICLES = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")
_VOCAB = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_vocab.txt")
_NB = os.path.expanduser("~/.neurobase")

# ═══════════════════════════════════════════════
# 本地标签词库
# ═══════════════════════════════════════════════

_TAG_MAP = {
    "免费|不花钱|省钱|性价比|开源|free|open source":                    ["成本观", "性价比优先"],
    "付费|买|花钱|效率优先|buy|pay|subscription":                       ["成本观", "愿意投入"],
    "Python|Rust|Go|代码|code|编程":                                    ["技术选型", "工具偏好"],
    "自己|手写|不靠|本地|离线|local|offline|self-host":                 ["独立性", "动手派"],
    "不管了|随便|放弃|不纠结|whatever|give up|fine":                     ["决策疲劳", "红牌"],
}

_DIRECTION_MAP = {
    "frugal": ["免费", "不花钱", "省钱", "性价比", "开源", "自己搞", "本地", "free", "open source", "self-host"],
    "spend":  ["花钱", "付费", "买", "效率优先", "buy", "pay", "subscription"],
    "drift":  ["不管了", "随便", "放弃", "不纠结", "whatever", "give up", "fine"],
}


# ═══════════════════════════════════════════════
# 本地标签（baseline）
# ═══════════════════════════════════════════════

def _tag_local(choice: str) -> str:
    tags = []
    seen = set()
    for pattern, tag_list in _TAG_MAP.items():
        if any(w in choice.lower() for w in pattern.split("|")):
            for t in tag_list:
                if t not in seen:
                    tags.append(t)
                    seen.add(t)
    return ",".join(tags) if tags else ""


# ═══════════════════════════════════════════════
# 选项提取（本地快速）
# ═══════════════════════════════════════════════

def _extract_options(question: str) -> str:
    """从问题中拆选项：'A还是B'→'A_B'"""
    parts = [p.strip() for p in question.replace("还是", "|").replace(" or ", "|").split("|")]
    return "_".join(p[:20] for p in parts[:5] if p)


def _detect_chain(text: str) -> list[str]:
    """
    决策链条检测——不判对错，记录全过程。
    
    "选A吧...还是B了...最后搞了C...算了还是A好"
      → ['A', 'B', 'C', 'A']
    
    真实人类的决策是波浪形的——犹豫、试探、回退。
    记忆体的责任是记录这个波浪，LLM 吃进画像+链条来推断倾向。
    """
    import re
    
    chain = []
    seen = set()
    
    # ① 显式选择
    choice_patterns = [
        r"(?:我?选|就|还是|决定|定了|要)(?:择|用|搞|弄)?\s*[「『\"]?(.{1,30}?)[」『\"]?(?:吧|了|的|好|行|可以)",
        r"还是\s*(.{1,15})\s*(?:吧|好|了)",
        r"(?:那就|就|那)\s*[「『\"]?(.{1,20}?)[」『\"]?\s*(?:吧|了)",
        r"我?(?:决定|打算|准备)\s*(.{1,30})",
        r"(?:最后|最终|定了|确定了|拍板)\s*(?:还?是|就|搞|选|用|要)?\s*[「『\"]?(.{1,30}?)[」『\"]?\s*(?:吧|了|的|好|行)",
    ]
    for pattern in choice_patterns:
        for m in re.finditer(pattern, text):
            choice = m.group(1).strip()
            if len(choice) >= 1 and choice not in ("还是", "就是", "不是"):
                chain.append(choice)
    
    # ② 命令式拍板
    action_pattern = r"(?:用|装|上|搞|跑|开|关|删|加|换|切)\s*[「『\"]?(.{1,20}?)[」『\"]?\s*(?:吧|了|的|掉)"
    for m in re.finditer(action_pattern, text):
        choice = m.group(1).strip()
        if len(choice) >= 2:
            chain.append(choice)
    
    # ③ 放弃信号
    give_up = ["不管了", "随便", "就那样", "算了", "不搞了", "放弃"]
    for g in give_up:
        if g in text:
            chain.append(g)
    
    return chain


def _chain_summary(chain: list[str]) -> str:
    """链条摘要：'A → B → C → 回到A'"""
    if not chain:
        return ""
    if len(chain) == 1:
        return chain[0]
    # 去相邻重复
    compact = [chain[0]]
    for c in chain[1:]:
        if c != compact[-1]:
            compact.append(c)
    if len(compact) == 1:
        return compact[0]
    # 检测回退：最后一个回到了之前出现过的
    if len(compact) >= 2 and compact[-1] in compact[:-1]:
        return " → ".join(compact) + f"  回到{compact[-1]}"
    return " → ".join(compact)


# ═══════════════════════════════════════════════
# 第三层全量上下文——喂给 LLM 自己推断
# ═══════════════════════════════════════════════

def _read_context() -> str:
    """采集第三层四支柱全部数据，给 LLM 做深层推断。"""
    parts = []

    # 1. 画像（认知内核 + 交互协议）
    persona_path = os.path.join(_NB, "persona", "persona.md")
    if os.path.exists(persona_path):
        with open(persona_path, "r", encoding="utf-8") as f:
            content = f.read()
        # 只取最关键的段落——认知内核和交互协议
        for section in ["🟡 交互协议", "🔴 认知内核", "基础锚点"]:
            start = content.find(f"## {section}")
            if start >= 0:
                end = content.find("\n## ", start + 10)
                parts.append(content[start:end if end > 0 else start + 800])

    # 2. 近期决策粒子（最近 20 条）
    if os.path.exists(_PARTICLES):
        with open(_PARTICLES, "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]
        if lines:
            parts.append("## 近期决策粒子\n" + "".join(lines))

    # 3. 搜索权重（最近热门话题）
    wf = os.path.join(_NB, "search_weights.txt")
    if os.path.exists(wf):
        with open(wf, "r", encoding="utf-8") as f:
            parts.append("## 搜索权重\n" + f.read()[:500])

    # 4. 织布机矛盾告警
    wl = os.path.join(_NB, "weave_alerts.txt")
    if os.path.exists(wl):
        with open(wl, "r", encoding="utf-8") as f:
            parts.append("## 织布机矛盾\n" + f.read()[:500])

    return "\n\n".join(parts)


# ═══════════════════════════════════════════════
# LLM 深层推断标签
# ═══════════════════════════════════════════════

def _tag_llm(question: str, choice: str) -> str:
    """
    让 LLM 吃进画像+阶段+粒子+织布机，自己推断深层动机。
    不抄用户表面理由——用第三层所有数据交叉判断。
    """
    try:
        from sandglass_think import _llm

        context = _read_context()
        options = _extract_options(question)

        system = (
            "你是深层决策分析师。用户做了一个选择，你拥有用户的完整画像、近期决策历史、"
            "搜索权重和矛盾告警。你的任务不是复述用户的表面理由——而是用所有这些数据，"
            "推断他做这个选择的**真实深层动机**。\n\n"
            "推断维度：\n"
            "- 情绪状态（压力？开心？焦虑？生理期？）\n"
            "- 阶段特征（疯狂建设期？调整期？）\n"
            "- 偏移趋势（省钱→愿意投入→红牌？）\n"
            "- 认知惯性（完美主义？囤积癖？社恐式独立？）\n\n"
            "输出格式：只返回3-5个深层标签，逗号分隔。标签要有洞察力、有人味。\n"
            "例如：补偿心理(压力期),囤积式省钱,经期偏好,表演型效率,深夜决策疲劳\n"
            "不要解释，不要复述用户说的理由。"
        )

        user_prompt = (
            f"可选选项：{options}\n"
            f"用户选择了：{choice}\n\n"
            f"== 用户全量上下文 ==\n{context[:4000]}"
        )

        result = _llm(system, user_prompt, max_tokens=80)
        if result:
            tags = [t.strip() for t in result.split(",") if t.strip()]
            return ",".join(tags[:5])
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════
# 自进化——LLM 标签学进本地词库
# ═══════════════════════════════════════════════

def _learn(tags: str, choice: str = "") -> None:
    """LLM 产出的标签 → 写入 vocab 文件，下次检索直接命中。"""
    if not tags:
        return
    existing = set()
    if os.path.exists(_VOCAB):
        with open(_VOCAB, "r", encoding="utf-8") as f:
            for line in f:
                t = line.strip()
                if t:
                    existing.add(t)
    new_tags = [t.strip() for t in tags.split(",") if t.strip() and t.strip() not in existing]
    if new_tags:
        with open(_VOCAB, "a", encoding="utf-8") as f:
            for t in new_tags:
                f.write(f"{t}\n")


# ═══════════════════════════════════════════════
# LLM 丰富选择原因
# ═══════════════════════════════════════════════

def _enrich_choice_with_llm(question: str, choice: str) -> str:
    """LLM 用第三层上下文解释为什么选这个——不抄表面理由。"""
    try:
        from sandglass_think import _llm

        context = _read_context()
        options = _extract_options(question)

        system = (
            "你是决策动机分析师。用户面临选择，他用上下文中的所有数据来推断"
            "用户选择某个选项的**真实深层原因**。不要复述用户说的理由——"
            "用画像+决策历史+偏移趋势+阶段特征自己推。\n"
            "输出：一句话，20字以内。例如：'压力期补偿心理'、'经期偏好甜食'、"
            "'疯狂建设期的完美主义'。不要解释，直接给结论。"
        )

        user_prompt = (
            f"可选：{options}\n用户选了：{choice}\n\n"
            f"上下文参考：{context[:3000]}"
        )

        result = _llm(system, user_prompt, max_tokens=40)
        if result and result.strip():
            return f"{choice}({result.strip()[:30]})"
    except Exception:
        pass
    return choice


# ═══════════════════════════════════════════════
# 双层标签融合
# ═══════════════════════════════════════════════

def _tag(question: str, choice: str) -> str:
    local = _tag_local(choice)
    llm_tags = _tag_llm(question, choice)

    if llm_tags:
        _learn(llm_tags, choice)
        local_set = set(local.split(",")) if local else set()
        llm_list = [t.strip() for t in llm_tags.split(",")]
        merged = (list(local_set) if local_set else []) + [t for t in llm_list if t not in local_set]
        return ",".join(merged[:5])

    return local if local else "未分类"


def _direction(choice: str) -> str:
    c = choice.lower()
    for d, words in _DIRECTION_MAP.items():
        if any(w in c for w in words):
            return d
    return "neutral"


def _infer_resolution(chain: list[str]) -> str:
    """
    LLM 吃进全链条 + 画像 + 阶段 + 历史粒子，推断真正的偏好倾向。
    
    "A → B → C → 回到A" → LLM 推断：
      - 试了B（贵/复杂）退回A（便宜/熟悉）→ 成本敏感 + 习惯偏好
      - 不是C不好，是A对他有安全感
    
    返回推理结论，无 LLM 或链条太短返回空。
    """
    if not chain or len(chain) < 2:
        return ""
    try:
        from sandglass_think import _llm
        
        context = _read_context()
        summary = _chain_summary(chain)
        
        system = (
            "你是行为模式分析师。用户做了一串决策：犹豫、试探、回退。"
            "结合他的画像、决策历史、偏移趋势，推断这条链条背后揭示的深层偏好。\n\n"
            "不要复述链条内容。推断维度：\n"
            "- 为什么最后回了某个选项？（成本？习惯？安全感？完美主义？）\n"
            "- 中间试探的选项暴露了什么倾向？（想突破但不敢？好奇但克制？）\n"
            "- 下次遇到类似选择，该怎么服务他？（直接给什么？先过滤什么？）\n\n"
            "输出：一句话，30字以内。格式：'倾向于XX，下次直接给XX'"
        )
        
        user_prompt = (
            f"决策链条：{summary}\n"
            f"全链条：{' → '.join(chain)}\n\n"
            f"== 用户上下文 ==\n{context[:3000]}"
        )
        
        result = _llm(system, user_prompt, max_tokens=80)
        if result and result.strip():
            return result.strip()[:60]
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════
# 落粒子
# ═══════════════════════════════════════════════

def log(question: str, choice: str, ts: str = "") -> None:
    """
    落一粒决策。记录全链条，LLM 推断倾向。
    
    格式：早饭_午饭 | A → B → A  回到A(成本敏感) | furgal | 成本观,习惯偏好
              ↑选项     ↑决策链条+推断                   ↑方向  ↑标签
    """
    if not ts:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    options = _extract_options(question)
    tags = _tag(question, choice)
    direction = _direction(choice)
    
    # 链条 + LLM 推断
    chain = _detect_chain(question + " " + choice)
    if chain:
        summary = _chain_summary(chain)
        inference = _infer_resolution(chain) if _has_llm() else ""
        resolved = f"{summary}  ({inference})" if inference else summary
    else:
        resolved = choice

    record = f"{options} | {resolved} | {direction} | {tags}"

    os.makedirs(os.path.dirname(_PARTICLES), exist_ok=True)
    with open(_PARTICLES, "a", encoding="utf-8") as f:
        f.write(f"{ts} | {record}\n")

    feed_all(resolved, tags, direction)


def _has_llm() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENROUTER_API_KEY"))


# ═══════════════════════════════════════════════
# 读取 & 偏移比
# ═══════════════════════════════════════════════

def read(limit: int = 50) -> list:
    if not os.path.exists(_PARTICLES):
        return []
    with open(_PARTICLES, "r", encoding="utf-8") as f:
        return [l.strip().split(" | ") for l in f.readlines()[-limit:]]


def ratio() -> dict:
    particles = read(50)
    if not particles:
        return {"frugal": 0, "spend": 0, "drift": 0, "total": 0}
    counts = {"frugal": 0, "spend": 0, "drift": 0}
    for p in particles:
        # 格式：ts | options | enriched_choice | direction | tags
        d = p[3] if len(p) > 3 else "neutral"
        if d in counts:
            counts[d] += 1
    total = sum(counts.values())
    return {
        "frugal": round(counts["frugal"] / total * 100) if total else 0,
        "spend": round(counts["spend"] / total * 100) if total else 0,
        "drift": round(counts["drift"] / total * 100) if total else 0,
        "total": total,
    }


# ═══════════════════════════════════════════════
# 四支柱反哺
# ═══════════════════════════════════════════════

def feed_all(choice: str, tags: str, direction: str) -> None:
    feed_persona(tags)
    _update_search_weights(tags)
    _weave_check(tags, direction)


def feed_persona(tags: str) -> None:
    p = os.path.join(_NB, "persona", "persona.md")
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    layer_map = {
        "成本观": "🔴 认知内核", "性价比优先": "🔴 认知内核",
        "技术选型": "🔵 兴趣图谱", "工具偏好": "🔵 兴趣图谱",
        "独立性": "🔴 认知内核", "动手派": "🔴 认知内核",
        "决策疲劳": "🟡 交互协议", "红牌": "🟡 交互协议",
    }
    added = []
    for tag in tags.split(","):
        tag = tag.strip()
        if layer_map.get(tag) and tag not in content:
            added.append(f"- [{datetime.now():%Y-%m-%d}] {tag}（决策粒子提炼）")
    if added:
        insert = content.find("## 🔴 认知内核")
        if insert < 0:
            insert = len(content)
        new = content[:insert] + "\n".join(added) + "\n" + content[insert:]
        with open(p, "w", encoding="utf-8") as f:
            f.write(new)


def _update_search_weights(tags: str) -> None:
    wf = os.path.join(_NB, "search_weights.txt")
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


def _weave_check(tags: str, direction: str) -> None:
    p = os.path.join(_NB, "persona", "persona.md")
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        persona = f.read()
    contra = []
    if "成本观" in tags and "性价比优先" in persona and direction == "spend":
        contra.append("画像:性价比优先 ↔ 决策:愿意投入")
    if "决策疲劳" in tags and "追根溯源" in persona:
        contra.append("画像:追根溯源 ↔ 决策:红牌放弃")
    if contra:
        wl = os.path.join(_NB, "weave_alerts.txt")
        with open(wl, "a", encoding="utf-8") as f:
            for c in contra:
                f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {c}\n")
