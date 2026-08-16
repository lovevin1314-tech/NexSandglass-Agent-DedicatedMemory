"""NexSandglass L3 — weave_l3"""
import os, re, json, logging
from sandglass_paths import _NB
from datetime import datetime, timezone
from sandglass_vault import _tokenize
from offset_signals import _OFFSET_SIGNALS

_VAULT = _NB
_PERSONA_DIR = os.path.join(_VAULT, "persona")
_PERSONA = os.path.join(_PERSONA_DIR, "persona.md")
_PERSONA_TIMELINE = os.path.join(_PERSONA_DIR, "persona-timeline.jsonl")
_DECISION_LOG = os.path.join(_PERSONA_DIR, "decision-log.jsonl")
logger = logging.getLogger(__name__)

# Lazy imports — avoid circular dependency with sandglass_think

try:
    from sandglass_think import _fail_open, comprehensive_offset, cross_stage_offset, stage_list, search_with_stage_label, weave_links
except ImportError:
    _fail_open = lambda d: lambda f: f
    comprehensive_offset = lambda: {"offset": 0, "direction": "neutral", "sample": 0}
    cross_stage_offset = lambda *a, **kw: {}
    stage_list = lambda: []
    search_with_stage_label = lambda *a, **kw: []
    weave_links = lambda: {"linked": False}

@_fail_open({})
def weave_insight(topic: str) -> dict:
    """织布：给定一个话题，从四个支柱分别取线，织成合成洞察。
    返回 {persona_view, offset_view, search_view, thread_view, synthesis}"""
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

    # V2.9.7 第四支柱：织线因果链（按话题查，有数据门控）
    result["thread_view"] = ""
    try:
        from weavethread import wthread_stats, wthread_to_weave
        stats = wthread_stats()
        if stats["total_triples"] >= 20:
            thread = wthread_to_weave(entity=topic if topic else "user")
            if thread.get("summary"):
                result["thread_view"] = thread["summary"]
    except Exception:
        logger.warning(f"weave_insight: 静默异常", exc_info=True)
        pass

    # 织：四条线合成
    synthesis = []
    if result["persona_view"] and result["persona_view"][0] != "画像中无相关内容":
        synthesis.append("画像说：" + result["persona_view"][0][:80])
    if result["offset_view"]["evolution"]:
        synthesis.append("偏移说：" + result["offset_view"]["evolution"])
    if sands:
        synthesis.append("沙子中有 " + str(len(sands)) + " 条相关记录")
    if result["thread_view"]:
        synthesis.append("织线：" + result["thread_view"][:100])

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
    try:
        from scene_l3 import scene_dominance
    except ImportError:
        logger.warning(f"weave_contradiction: 局部导入失败: from scene_l3 import scene_dominance", exc_info=True)
        from sandglass_think import scene_dominance
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
    try:
        from sandglass_think import decision_stability
    except ImportError:
        logger.warning(f"weave_contradiction: 局部导入失败: from sandglass_think import decision_stability", exc_info=True)
        decision_stability = lambda: {"overall": {"volatility": 0}}
    stab = decision_stability()
    try:
        from scene_l3 import stage_switch_prediction
    except ImportError:
        logger.warning(f"weave_contradiction: 局部导入失败: from scene_l3 import stage_switch_prediction", exc_info=True)
        stage_switch_prediction = lambda: {"predicted": False}
    pred = stage_switch_prediction()
    if stab["overall"]["volatility"] >= 40 and not pred.get("predicted"):
        conflicts.append({
            "pillar_a": "偏移率（稳定性）", "pillar_b": "偏移率（预测）",
            "conflict": "决策波动" + str(stab["overall"]["volatility"]) + "，但预测说短期不切换",
            "evidence": "波动值高但斜率不足",
        })

    # 矛盾4：3D 立体注解 vs 2D 偏移
    try:
        from sandglass_think import _latest_annotation
    except ImportError:
        logger.warning(f"weave_contradiction: 局部导入失败: from sandglass_think import _latest_annotation", exc_info=True)
        _latest_annotation = lambda: {}
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
    ), "interlinks": weave_links() if stage_list() and len(stage_list()) >= 2 else {"linked": False}}

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

def weave_graph(question: str, max_hops: int = 3) -> dict:
    """
    因果图——回答"为什么"的问题。
    
    从沙子/决策粒子/标签三个源出发，用 CTE 递归追溯因果链。
    零额外依赖——SQLite WITH RECURSIVE 内置。
    
    返回 {chains, root_causes, insight}
    """
    try:
        from sandglass_sqlite import _get_db
        db = _get_db()
        cursor = db.cursor()
        
        # 拆问题为搜索词
        keywords = [w for w in re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', question) if len(w) > 1][:3]
        if not keywords:
            keywords = [question[:20]]
        
        # CTE 递归：从匹配关键词的沙子和决策粒子出发，追溯关联
        chains = []
        root_causes = set()
        
        for kw in keywords:
            try:
                cursor.execute("""
                    WITH RECURSIVE trace(id, content, source, depth, path) AS (
                        -- 起点：匹配关键词的沙子行
                        SELECT rowid, content, 'sand', 0, content
                        FROM sandglass_fts
                        WHERE content LIKE '%' || ? || '%'
                        LIMIT 10
                        
                        UNION ALL
                        
                        -- 第一跳：包含同一关键词的相邻沙子
                        SELECT s.rowid, s.content, 'adjacent', trace.depth + 1,
                               trace.path || ' -> ' || s.content
                        FROM sandglass_fts s
                        JOIN trace ON s.content LIKE '%' || ? || '%'
                        WHERE trace.depth < ?
                        LIMIT 5
                    )
                    SELECT depth, source, path FROM trace ORDER BY depth
                """, (kw, kw, max_hops))
                
                for depth, source, path in cursor.fetchall():
                    chains.append({"keyword": kw, "depth": depth, "source": source,
                                   "path": path[:200] if path else ""})
                    # 提取根源关键词
                    if depth == max_hops and path:
                        root_word = path.split(' -> ')[-1][:30]
                        root_causes.add(root_word)
            except Exception:
                continue
        
        cursor.close()
        
        # 补充：从决策粒子标签追溯
        dp_roots = set()
        dp_path = os.path.join(_NB, "decision_particles.txt")
        if os.path.exists(dp_path):
            with open(dp_path, "r", encoding="utf-8") as f:
                dp_lines = f.readlines()[-30:]
            for kw in keywords:
                for line in dp_lines:
                    if kw in line.lower():
                        parts = line.strip().split(" | ")
                        if len(parts) >= 5:
                            dp_roots.add(parts[4][:50])  # 标签作为根源
        
        all_roots = root_causes | dp_roots
        
        # 生成洞察
        insight_parts = []
        if all_roots:
            insight_parts.append(f"追溯到最后：{'、'.join(list(all_roots)[:5])}")
        if chains:
            insight_parts.append(f"共 {len(chains)} 跳因果链")
        if not chains and not all_roots:
            insight_parts.append("数据不足，多积累几天沙子就能追溯了")
        
        return {
            "question": question,
            "chains": chains[:10],
            "root_causes": list(all_roots)[:10],
            "total_hops": len(chains),
            "insight": "；".join(insight_parts) if insight_parts else "暂无因果链",
        }
    except Exception:
        logger.warning(f"weave_graph: 局部导入失败: from sandglass_sqlite import _get_db", exc_info=True)
        return {"question": question, "chains": [], "root_causes": [], "total_hops": 0,
                "insight": "织布机因果图暂不可用（需要 sandglass_sqlite FTS5 索引）"}

def weave_output(query: str = "", limit: int = 5) -> dict:
    """V2.9.5: 织布机统一输出 → 搜索滤镜素材。
    整合因果链 + 矛盾检测 + 场景感知 + 偏移率 + 情绪，
    返回 {insight, contradictions, causal, scene_context, offset_guide, emotion_note}
    """
    import logging
    logger = logging.getLogger(__name__)
    
    result = {
        "insight": "",
        "contradictions": [],
        "causal": [],
        "scene_context": "",
        "offset_guide": "",
        "emotion_note": "",
        "keywords": [],
    }
    
    # 1. 因果洞察
    try:
        if query:
            insight = weave_insight(query)
            if insight and insight.get("synthesis"):
                result["insight"] = insight["synthesis"][:300]
    except Exception:
        logger.warning("织布机因果洞察失败", exc_info=True)
    
    # 2. 矛盾检测
    try:
        contra = weave_contradiction()
        if contra and contra.get("conflicts"):
            result["contradictions"] = contra["conflicts"][:3]
    except Exception:
        logger.warning("织布机矛盾检测失败", exc_info=True)
    
    # 3. 场景感知
    try:
        from scene_l3 import scene_current
        scenes = scene_current()
        if scenes:
            result["scene_context"] = " · ".join(scenes[:3])
            result["keywords"].extend(scenes[:3])
    except Exception:
        logger.warning(f"weave_output: 静默异常", exc_info=True)
        pass
    
    # 4. 偏移率方向
    try:
        from sandglass_think import comprehensive_offset
        off = comprehensive_offset()
        direction = off.get("direction", "")
        offset_val = off.get("offset", 0)
        if direction == "frugal":
            result["offset_guide"] = f"省钱倾向({offset_val:+d}%) — 偏好免费/本地/开源方案"
        elif direction == "spend":
            result["offset_guide"] = f"愿投倾向({offset_val:+d}%) — 愿意为效率/质量付费"
        elif direction == "drift":
            result["offset_guide"] = f"放弃倾向({offset_val:+d}%) — 可能厌倦或想换方向"
    except Exception:
        logger.warning(f"weave_output: 静默异常", exc_info=True)
        pass
    
    # 5. 情绪温度
    try:
        from sandglass_think import _emotional_entropy
        ent = _emotional_entropy()
        if ent < 0.5:
            result["emotion_note"] = "状态: 平稳 — 理性主导"
        elif ent < 1.0:
            result["emotion_note"] = "波动期 — 可能犹豫或感性"
        else:
            result["emotion_note"] = "高熵期 — 情绪波动大，谨慎建议"
    except Exception:
        logger.warning(f"weave_output: 静默异常", exc_info=True)
        pass
    
    # 去重关键词
    result["keywords"] = list(dict.fromkeys(result["keywords"][:10]))
    
    return result


def _weave_estimate_tokens(text: str) -> int:
    """复用 discipline._estimate_tokens；不可用时退化为字符数。"""
    try:
        from discipline import _estimate_tokens
        return int(_estimate_tokens(text or ""))
    except Exception:
        return len(str(text or ""))


def _weave_source_text(full_line: str) -> str:
    """取影子沙关联的沙子行正文，去掉 [action] 前缀并压平空白。"""
    try:
        from shadow_sand import _content_part
        text = _content_part(full_line or "").strip()
    except Exception:
        text = (full_line or "").strip()
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _weave_context_around(text: str, needle: str, radius: int = 8) -> str:
    """围绕实体/标签截取 ≤2*radius 字上下文，体现跨时间交织而不是裸罗列。"""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return "近期沙子"
    if not needle:
        return text[: radius * 2]
    idx = text.find(needle)
    if idx < 0:
        return text[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(needle) + radius)
    return text[start:end].strip() or "近期沙子"


def _weave_entity_context(name: str, line_nums: str, lines: list, radius: int = 8) -> str:
    """为实体寻找其所在沙行，返回实体附近的上下文片段。"""
    fallback = ""
    try:
        from shadow_sand import _is_system_tool_content
        for raw in str(line_nums or "").split(","):
            raw = raw.strip()
            if not raw.isdigit():
                continue
            idx = int(raw) - 1
            if idx < 0 or idx >= len(lines):
                continue
            full = lines[idx]
            if _is_system_tool_content(full):
                continue
            text = _weave_source_text(full)
            if not fallback and text:
                fallback = _weave_context_around(text, "", radius)
            if name and name in text:
                return _weave_context_around(text, name, radius)
    except Exception:
        logger.warning("_weave_entity_context 失败", exc_info=True)
    return fallback or "近期沙子"


def _weave_fact_source_context(category: str, tag: str, radius: int = 8) -> str:
    """为事实标签回找其来源沙行，返回标签附近的上下文片段。"""
    try:
        from shadow_sand import _get_conn, _sandglass_lines, _is_system_tool_content, _tag_quality, extract_tags
        lines = _sandglass_lines()
        if not lines:
            return "近期沙子"
        rows = _get_conn().execute(
            "SELECT line_num, tags FROM fact_tags "
            "WHERE category = ? AND tags != '' AND tags != '未分类' "
            "AND line_num > 0 AND line_num <= ? "
            "ORDER BY line_num DESC LIMIT 200",
            (category, len(lines)),
        ).fetchall()
        for ln, tags in rows:
            if 0 < ln <= len(lines) and _is_system_tool_content(lines[ln - 1]):
                continue
            norm_tags = []
            for t in (tags or "").split(","):
                ok, norm = _tag_quality(t)
                if ok:
                    norm_tags.append(norm)
            if tag not in norm_tags:
                continue
            text = _weave_source_text(lines[ln - 1])
            if tag in extract_tags(text, limit=100):
                return _weave_context_around(text, tag, radius)
            if text:
                return _weave_context_around(text, "", radius)
    except Exception:
        logger.warning("_weave_fact_source_context 失败", exc_info=True)
    return "近期沙子"


def weave_entities_with_context(limit: int = 5, seen_facts: set = None, max_tokens: int = None, radius: int = 8) -> list:
    """织布机加工层：高信实体 + 场景上下文。

    读 shadow_top_entities 结果，为每个实体关联其所在沙子行的附近上下文。
    输出如 `  黑咖啡 (场景: 主人: 喜欢黑咖啡)`，体现实体与场景的关系，
    而不是简单罗列实体名。
    """
    try:
        from shadow_sand import shadow_top_entities, _sandglass_lines
        rows = shadow_top_entities(limit=max(20, int(limit) * 4))
        lines = _sandglass_lines()
        seen = set(seen_facts or [])
        out = []
        used = 0
        for row in rows:
            if len(out) >= int(limit):
                break
            if not row or len(row) < 2:
                continue
            name = str(row[0]).strip()
            if not name or name.isdigit() or len(name) < 2 or name in seen:
                continue
            ctx = _weave_entity_context(name, row[1], lines, radius)
            line = f"  {name} (场景: {ctx})"
            cost = _weave_estimate_tokens(line)
            if max_tokens is not None:
                if out and used + cost > int(max_tokens):
                    break
                if cost > int(max_tokens):
                    continue
            out.append(line)
            seen.add(name)
            used += cost
        return out
    except Exception:
        logger.warning("weave_entities_with_context 失败", exc_info=True)
        return []


def weave_fact_categories_with_context(limit: int = 5, seen_facts: set = None, max_tokens: int = None, radius: int = 8) -> list:
    """织布机加工层：事实标签 + 来源上下文。

    读 shadow_top_fact_categories 结果，为每条分类标签回找来源沙行，
    输出 `  [偏好] 深色模式 (来源: 主人: 偏好深色模式)`。
    """
    try:
        from shadow_sand import shadow_top_fact_categories
        rows = shadow_top_fact_categories(limit=max(10, int(limit) * 2))
        seen = set(seen_facts or [])
        out = []
        used = 0
        total = 0
        for category, tags in rows:
            if total >= int(limit):
                break
            category = str(category or "").strip()
            for raw in str(tags or "").split(","):
                if total >= int(limit):
                    break
                tag = raw.strip()
                if not tag or tag in seen:
                    continue
                ctx = _weave_fact_source_context(category, tag, radius)
                line = f"  [{category}] {tag} (来源: {ctx})"
                cost = _weave_estimate_tokens(line)
                if max_tokens is not None:
                    if out and used + cost > int(max_tokens):
                        break
                    if cost > int(max_tokens):
                        continue
                out.append(line)
                seen.add(tag)
                used += cost
                total += 1
                if total >= int(limit):
                    break
        return out
    except Exception:
        logger.warning("weave_fact_categories_with_context 失败", exc_info=True)
        return []


def weave_search_filter(query: str = "") -> str:
    """V2.9.5: 织布机 → 搜索滤镜 格式化输出。
    返回 LLM 可注入的文本块。
    """
    w = weave_output(query)
    lines = []
    
    if w["insight"]:
        lines.append(f"状态: {w['insight'][:120]}")
    if w["contradictions"]:
        for c in w["contradictions"][:2]:
            if isinstance(c, dict) and c.get("conflict"):
                lines.append(f"矛盾: {c['conflict'][:100]}")
    if w["offset_guide"]:
        lines.append(w["offset_guide"])
    if w["emotion_note"]:
        lines.append(w["emotion_note"])
    if w["scene_context"]:
        lines.append(f"场景: {w['scene_context']}")
    
    return "\n".join(lines) if lines else ""
