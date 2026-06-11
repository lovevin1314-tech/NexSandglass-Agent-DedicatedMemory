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


def _is_decision(text: str) -> bool:
    """
    粗筛——快速判断消息是不是决策。
    过滤条件：去掉纯指令、闲话、确认回复。
    保留条件：包含选择信号（中英双语）。
    """
    import re
    
    # 纯指令/闲话——不是决策
    noise = [
        r"^(推|OK|好的|确认|删|发|等|继续|下一个)[吧了]?$",
        r"^(还有|还有吗|有没有|在吗|好了吗)[？?]?$",
        r"^[a-zA-Z]{1,3}$",  # 单字母/短英文
    ]
    for n in noise:
        if re.match(n, text.strip()):
            return False
    
    # 选择信号——是决策
    signals = [
        r"(?:还是|或者|or|either).{2,30}(?:还是|或者|or|either)?",  # A还是B
        r"(?:选|用|装|换|搞|跑|试|买|做)(?:择|了|这个|哪个)?\s*[。！，\n]?",
        r"(?:就用|就选|就搞|决定|定了|确定)\s*.{1,20}",
        r"(?:go with|choose|pick|decide|switch to|use)\s+.{1,30}",
        r"(?:不管了|放弃|算了|随便|就那样|能用就行)",
        r"(?:give up|whatever|never mind|fine|let's just)",
    ]
    for s in signals:
        if re.search(s, text, re.IGNORECASE):
            return True
    
    return False


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
    
    # ① 显式选择 —— 中英双语
    choice_patterns = [
        # 中文
        r"(?:我?选|就|还是|决定|定了|要)(?:择|用|搞|弄)?\s*[「『\"]?(.{1,30}?)[」『\"]?(?:吧|了|的|好|行|可以)",
        r"还是\s*(.{1,15})\s*(?:吧|好|了)",
        r"(?:那就|就|那)\s*[「『\"]?(.{1,20}?)[」『\"]?\s*(?:吧|了)",
        r"我?(?:决定|打算|准备)\s*(.{1,30})",
        r"(?:最后|最终|定了|确定了|拍板)\s*(?:还?是|就|搞|选|用|要)?\s*[「『\"]?(.{1,30}?)[」『\"]?\s*(?:吧|了|的|好|行)",
        # 英文
        r"(?:I'?ll\s+)?go\s+with\s+(.{1,30})",
        r"choose\s+(.{1,30})",
        r"(?:let'?s|I'?ll)\s+(?:do|try|use|take|pick)\s+(.{1,30})",
        r"(?:decided|going\s+with|picking)\s+(.{1,30})",
        r"(?:actually|scratch\s+that|on\s+second\s+thought|never\s+mind)[,.\s]*(?:let'?s\s+)?(?:do|go\s+with|try|use|take)\s+(.{1,30})",
    ]
    for pattern in choice_patterns:
        for m in re.finditer(pattern, text):
            choice = m.group(1).strip()
            if len(choice) >= 1 and choice.lower() not in ("还是", "就是", "不是", "just", "not", "or", "maybe", "either"):
                chain.append(choice)
    
    # ② 命令式拍板 —— 中英双语
    action_patterns = [
        r"(?:用|装|上|搞|跑|开|关|删|加|换|切)\s*[「『\"]?(.{1,20}?)[」『\"]?\s*(?:吧|了|的|掉)",
        r"(?:do|run|use|install|start|stop|delete|add|switch)\s+(.{1,20})",
    ]
    for pattern in action_patterns:
        for m in re.finditer(pattern, text):
            choice = m.group(1).strip()
            if len(choice) >= 2:
                chain.append(choice)
    
    # ③ 放弃信号 —— 中英双语
    give_up = ["不管了", "随便", "就那样", "算了", "不搞了", "放弃", "whatever", "never mind", "fine", "give up", "I'm done"]
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
        for section in ["🟡 交互协议", "🔴 认知内核", "🟢 基础锚点"]:
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


def _infer_local(chain: list[str]) -> str:
    """
    本地模糊推断——不用 LLM，靠三层结构已有数据。
    
    策略：
      ① 链条模式匹配：回退→习惯偏好，多条→选择困难，放弃→决策疲劳
      ② 关键词标签：拆每个选项的关键词，匹配画像已有标签
      ③ 历史粒子比对：最近50条粒子找相似模式
    """
    if not chain or len(chain) < 2:
        return ""
    
    hints = []
    compact = [chain[0]]
    for c in chain[1:]:
        if c != compact[-1]:
            compact.append(c)
    
    # ① 链条模式
    if len(compact) >= 2 and compact[-1] in compact[:-1]:
        hints.append("习惯回退")  # A→B→A 或 A→B→C→A
    if len(compact) >= 3:
        hints.append("选择困难")  # 3个以上不同选择
    if any(g in " ".join(chain) for g in ["不管了", "放弃", "随便", "算了"]):
        hints.append("决策疲劳")
    
    # ② 关键词标签——拆选项匹配本地词库
    for item in compact:
        local = _tag_local(item)
        if local and local != "":
            for t in local.split(","):
                t = t.strip()
                if t and t not in hints:
                    hints.append(t)
    
    # ③ 历史比对——最近粒子找共性
    particles = read(20)
    if particles:
        # 找和当前链条第一个选项相同的粒子
        first = compact[0]
        similar = [p for p in particles if len(p) > 1 and first[:4] in (p[1] if len(p)>1 else "")]
        if similar:
            common_directions = [p[3] for p in similar if len(p)>3]
            if common_directions:
                most = max(set(common_directions), key=common_directions.count)
                direction_label = {"frugal": "成本敏感", "spend": "愿意投入", "drift": "红牌倾向"}.get(most, "")
                if direction_label and direction_label not in hints:
                    hints.append(direction_label)
    
    if hints:
        return f"倾向{','.join(hints[:3])}"
    return ""


def _infer_resolution(chain: list[str]) -> str:
    """
    决策链条推断——LLM 优先，本地兜底。
    
    LLM：吃进画像+阶段+历史粒子，深层推断倾向
    本地：关键词+链条模式+历史比对，模糊画像
    """
    if not chain or len(chain) < 2:
        return ""
    
    # LLM 优先
    try:
        from sandglass_think import _llm
        
        context = _read_context()
        summary = _chain_summary(chain)
        
        system = (
            "你是行为模式分析师。用户做了一串决策：犹豫、试探、回退。"
            "结合他的画像、决策历史、偏移趋势，推断这条链条背后揭示的深层偏好。"
            "不要复述链条内容。推断维度：为什么回退？试探暴露了什么？下次怎么服务他？"
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
    
    # 本地兜底——三层结构已有数据
    return _infer_local(chain)


_ECHO_WIND = os.path.join(os.path.expanduser("~"), ".neurobase", "echo_wind.jsonl")

def _infer_sentiment(question: str) -> str:
    """从决策粒子上下文推断情感风。"""
    positive = ["太棒", "太好了", "终于", "完美", "好主意", "聪明", "厉害"]
    negative = ["烦死", "太难", "不好", "失败", "后悔", "算了", "没用"]
    for w in positive:
        if w in question: return "正面"
    for w in negative:
        if w in question: return "负面"
    return ""

def _echo_spread(sentiment: str, options: str) -> None:
    """回音折扩散——情感风落到语义邻居。"""
    if not sentiment: return
    entry = {"ts": datetime.now().isoformat(), "sentiment": sentiment,
             "options": options,
             "spread_weight": 1.3 if sentiment == "正面" else 0.8}
    os.makedirs(os.path.dirname(_ECHO_WIND), exist_ok=True)
    with open(_ECHO_WIND, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════
# 落粒子
# ═══════════════════════════════════════════════

def log(question: str, choice: str, ts: str = "", chain: list = None) -> None:
    """
    落一粒决策。记录全链条，LLM 推断倾向。
    
    格式：早饭_午饭 | A → B → A  回到A(成本敏感) | furgal | 成本观,习惯偏好
              ↑选项     ↑决策链条+推断                   ↑方向  ↑标签
    
    chain: 调用方已检测的决策链条（如 pulse.py 从全量消息检测）。
           若未提供，内部从 question+choice 重新检测。
    """
    if not ts:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    options = _extract_options(question)
    tags = _tag(question, choice)
    direction = _direction(choice)
    
    # 链条——优先用调用方传入的（无截断信息丢失）
    if chain is None:
        chain = _detect_chain(question + " " + choice)
    if chain:
        summary = _chain_summary(chain)
        inference = _infer_resolution(chain) if _has_llm() else ""
        resolved = f"{summary}  ({inference})" if inference else summary
    else:
        resolved = choice

    # 情绪标记
    emotion_tag = "neutral"
    try:
        from emotion_vocab import detect as emotion_detect
        det = emotion_detect(question + " " + choice)
        if det.get("mood"): emotion_tag = det["mood"]
    except: pass
    record = f"{options} | {resolved} | {direction} | {emotion_tag} | {tags}"

    os.makedirs(os.path.dirname(_PARTICLES), exist_ok=True)
    with open(_PARTICLES, "a", encoding="utf-8") as f:
        f.write(f"{ts} | {record}\n")

    # 影子沙同步
    try:
        from shadow_sand import shadow_index
        shadow_index(choice, "decision", tags)
    except: pass

    feed_all(resolved, tags, direction)

    # 幽灵灵魂——每次落粒子都投射影子画像（基于情感风持续生长）
    try:
        from sandglass_think import persona_project, comprehensive_offset
        off = comprehensive_offset()
        if off.get("direction") and off["direction"] != "neutral":
            persona_project(off["direction"], off.get("offset", 0))
    except: pass

    # 回音折回读——落粒子时读取情感残留
    try:
        echo_path = os.path.join(os.path.expanduser("~"), ".neurobase", "echo_wind.jsonl")
        if os.path.exists(echo_path):
            qwords = set(question.lower().split())
            with open(echo_path, "r", encoding="utf-8") as ef:
                for eline in ef:
                    try:
                        rec = json.loads(eline.strip())
                        ow = set(rec.get("options", "").lower().split())
                        if len(qwords & ow) >= 2 and rec.get("sentiment"):
                            # 回音残留——追加到决策粒子
                            with open(_PARTICLES, "a", encoding="utf-8") as af:
                                af.write(f"{ts} | echo_wind | {rec['sentiment']}({rec.get('spread_weight',1.0)}) | echo | 回音折残留\n")
                            break
                    except: pass
    except: pass


def _has_llm() -> bool:
    """统一LLM检测——从offset_signals获取。"""
    try:
        from offset_signals import _LLM_KEY
        return bool(_LLM_KEY)
    except ImportError:
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
    """动态织布——从_OFFSET_SIGNALS源取信号，检测言行是否一致。"""
    p = os.path.join(os.path.expanduser("~"), ".neurobase", "persona", "persona.md")
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        persona = f.read()

    from offset_signals import _OFFSET_SIGNALS

    contra = []
    frugal_words = _OFFSET_SIGNALS.get("frugal", [])
    spend_words = _OFFSET_SIGNALS.get("spend", [])
    drift_all = (_OFFSET_SIGNALS.get("drift_放弃", []) +
                 _OFFSET_SIGNALS.get("drift_妥协", []) +
                 _OFFSET_SIGNALS.get("drift_烦躁", []))

    # 当前方向 vs 画像倾向——用源信号做语义匹配
    if direction == "spend":
        matched = [w for w in frugal_words if w in persona]
        if matched:
            contra.append(f"方向矛盾: 当前花钱 ↔ 画像倾向省钱({'、'.join(matched[:3])})")
    elif direction == "frugal":
        matched = [w for w in spend_words if w in persona]
        if matched:
            contra.append(f"方向矛盾: 当前省钱 ↔ 画像倾向花钱({'、'.join(matched[:3])})")
    elif direction == "drift":
        matched = [w for w in drift_all if w in persona]
        if matched:
            contra.append(f"⚠ 放弃信号出现——检查是否压力期 (画像有{'、'.join(matched[:3])})")

    # 标签里有的倾向但画像里找不到对应信号 → 画像滞后
    tag_frugal = any(t in tags for t in ["成本观", "性价比优先", "独立性", "动手派", "省钱"])
    tag_spend = any(t in tags for t in ["愿意投入", "花钱", "付费"])
    if tag_frugal and not any(w in persona for w in frugal_words):
        contra.append("标签倾向:省钱 ↔ 画像缺省钱信号——画像可能滞后")
    if tag_spend and not any(w in persona for w in spend_words):
        contra.append("标签倾向:花钱 ↔ 画像缺花钱信号——画像可能滞后")

    if contra:
        # 24h cooldown——drift告警不刷屏
        last_alert = os.path.join(os.path.expanduser("~"), ".neurobase", ".last_drift_alert")
        if os.path.exists(last_alert):
            if datetime.now().timestamp() - os.path.getmtime(last_alert) < 86400:
                return
        wl = os.path.join(os.path.expanduser("~"), ".neurobase", "weave_alerts.txt")
        with open(wl, "a", encoding="utf-8") as f:
            for c in contra:
                f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {c}\n")
        # 更新冷却时间戳（touch + mtime）
        if not os.path.exists(last_alert):
            with open(last_alert, "w") as f: pass
        os.utime(last_alert, None)
