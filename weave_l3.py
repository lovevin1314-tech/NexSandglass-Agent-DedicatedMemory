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
    from sandglass_think import _fail_open, _llm, comprehensive_offset, cross_stage_offset, stage_list, search_with_stage_label, weave_links
except:
    _fail_open = lambda d: lambda f: f
    _llm = None
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
    except:
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
    except:
        decision_stability = lambda: {"overall": {"volatility": 0}}
    stab = decision_stability()
    try:
        from scene_l3 import stage_switch_prediction
    except:
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
    except:
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
        pass
    
    # 2. 矛盾检测
    try:
        contra = weave_contradiction()
        if contra and contra.get("conflicts"):
            result["contradictions"] = contra["conflicts"][:3]
    except Exception:
        pass
    
    # 3. 场景感知
    try:
        from scene_l3 import scene_current
        scenes = scene_current()
        if scenes:
            result["scene_context"] = " · ".join(scenes[:3])
            result["keywords"].extend(scenes[:3])
    except Exception:
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
        pass
    
    # 去重关键词
    result["keywords"] = list(dict.fromkeys(result["keywords"][:10]))
    
    return result


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
