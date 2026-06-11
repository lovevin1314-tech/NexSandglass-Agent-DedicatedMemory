"""NexSandglass L3 — emotion_l3"""
import os, re, json, logging
from datetime import datetime, timezone
from sandglass_vault import _tokenize
from sandglass_paths import _NB

_VAULT = _NB
_PERSONA_DIR = os.path.join(_VAULT, "persona")
_PERSONA = os.path.join(_PERSONA_DIR, "persona.md")
_PERSONA_TIMELINE = os.path.join(_PERSONA_DIR, "persona-timeline.jsonl")
_DECISION_LOG = os.path.join(_PERSONA_DIR, "decision-log.jsonl")
logger = logging.getLogger(__name__)

# Lazy imports — avoid circular dependency
from sandglass_vault import recent, search as vs

import os as _os
from offset_signals import _LLM_KEY, _LLM_ENDPOINT, _LLM_MODEL
try:
    from sandglass_think import (
        _fail_open, _llm, _three_d_ready, _latest_annotation,
        _should_synthesize, _synthesize_3d, comprehensive_offset,
        _emotional_entropy, shadow_chart, stage_brief,
        weave_graph,
    )
    from persona_l3 import _WAVE_THRESHOLDS
    _3D_ANNOTATIONS = __import__('sandglass_think')._3D_ANNOTATIONS
except:
    _fail_open = lambda d: lambda f: f
    _llm = None
    _three_d_ready = lambda: False
    _latest_annotation = lambda: {}
    _should_synthesize = lambda: (False, "")
    _synthesize_3d = lambda **kw: {}
    comprehensive_offset = lambda: {"offset": 0, "direction": "neutral", "sample": 0}
    _WAVE_THRESHOLDS = {}
    _emotional_entropy = lambda: 0.0
    shadow_chart = lambda: ""
    stage_brief = lambda: ""
    weave_graph = lambda *a, **kw: {}
    _3D_ANNOTATIONS = ""

def entropy_mirror(question: str) -> dict:
    """
    熵镜决策——主人面临选择，织布机照见过去的影子。
    
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
        except Exception as e:
            logger.warning(f"entropy_mirror: 决策粒子文件解析失败: {e}")

    # ③ 当前偏移趋势
    try:
        comp = comprehensive_offset()
        if comp["sample"] >= 2:
            direction_cn = {"frugal": "省钱", "spend": "愿意投入", "drift": "放弃倾向"}
            d = direction_cn.get(comp["direction"], comp["direction"])
            result["current_trend"] = f"影子偏向{d}（{comp['offset']:+d}%），{comp['sample']}次决策"
    except Exception as e:
        logger.warning(f"entropy_mirror: 偏移趋势获取失败: {e}")

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
        except Exception as e:
            logger.warning(f"entropy_mirror: LLM增强失败: {e}")

    return result

def entropy_ghost(question: str) -> dict:
    """
    幽灵决策——'如果我当时选了另一个选项会怎样？'
    
    本地优先（80分）:
      ① 查历史类似决策的后续因果链（weave_graph）
      ② 查同标签决策的后续偏移模式
      ③ 基于历史数据推断
    
    LLM 增强（+120分）:
      喂上下文 → LLM 推演虚拟分支
    
    不论 2D 还是 3D，都标注'幽灵决策——纯虚拟推演，未修改任何数据'
    """
    # dp_read unused — 直接读文件替代

    result = {
        "question": question,
        "mode": "2D 本地",
        "similar_patterns": [],
        "causal_chain": [],
        "inference": "",
        "llm_enhanced": False,
    }

    # ① 查历史类似决策
    dp_path = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")
    if os.path.exists(dp_path):
        try:
            with open(dp_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            keywords = set(question.lower().split())
            matches = []
            for line in lines[-100:]:
                if any(kw in line.lower() for kw in keywords if len(kw) > 1):
                    parts = line.strip().split(" | ")
                    if len(parts) >= 5:
                        matches.append({
                            "ts": parts[0][:10],
                            "options": parts[1],
                            "choice": parts[2],
                            "direction": parts[3],
                            "tags": parts[4],
                        })
            result["similar_patterns"] = matches[-5:]
        except Exception as e:
            logger.warning(f"entropy_ghost: 决策粒子读取失败: {e}")

    # ② 查因果链（weave_graph 多跳追溯）
    try:
        graph = weave_graph(question[:20])
        if graph.get("chains"):
            result["causal_chain"] = [
                f"{n['depth']}跳: {n['keyword']}" for n in graph["chains"][:5]
            ]
    except Exception as e:
        logger.warning(f"entropy_ghost: 因果图追溯失败: {e}")

    # ③ 本地推断——基于真实历史模式
    if result["similar_patterns"]:
        directions = [p["direction"] for p in result["similar_patterns"]]
        tags_all = [p["tags"] for p in result["similar_patterns"]]
        most_dir = max(set(directions), key=directions.count) if directions else "?"
        if result["causal_chain"]:
            result["inference"] = (
                f"历史模式：类似决策的因果链显示→{result['causal_chain'][0]}。"
                f"最常出现的后续方向是'{most_dir}'。"
                f"镜像类比：如果当时这样选，画像可能会往'{most_dir}'方向移动。"
            )
        else:
            result["inference"] = (
                f"历史模式：类似决策后，最常出现的倾向是'{most_dir}'。"
                f"数据不够做因果追溯，但方向可参考。"
            )

    # ④ LLM 增强（200分）
    if _LLM_KEY and result["similar_patterns"]:
        try:
            persona_text = ""
            if os.path.exists(_PERSONA):
                with open(_PERSONA, "r", encoding="utf-8") as f:
                    persona_text = f.read()[:2000]

            past = "\n".join(
                f"- {p['ts']}: {p['options']} → {p['choice']} ({p['direction']})"
                for p in result["similar_patterns"]
            )

            system = (
                "你是幽灵决策推演师——模拟'如果当时选了另一个选项会怎样'。"
                "你有用户的完整画像和真实决策历史。"
                "基于他的行为模式推演虚拟分支。不要说'应该选什么'。"
                "标注这是纯虚拟推演。一句话，30字以内。"
            )

            llm_result = _llm(
                system,
                f"问题：{question}\n画像：{persona_text}\n历史类似决策：\n{past}\n本地推断：{result['inference']}",
                max_tokens=80,
            )
            if llm_result:
                result["inference"] = f"{llm_result.strip()}（幽灵决策——纯虚拟推演）"
                result["llm_enhanced"] = True
                result["mode"] = "3D LLM 增强"
        except Exception as e:
            logger.warning(f"entropy_ghost: LLM增强失败: {e}")

    return result

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
        sensitivity = _WAVE_THRESHOLDS.get(comp["direction"], {}).get("contour", 50)
        if comp["sample"] >= sensitivity:
            desc = f"最近{comp['sample']}条决策里——{d}的影子叠了{comp['sample']}层，轮廓已经成形了"
        else:
            desc = f"最近{comp['sample']}条决策里——{d}的影子正在叠加（{comp['sample']}/{sensitivity}）"
        return f"🫧 玻璃：{desc}"
    except Exception as e:
        logger.warning(f"glass_reminder: 2D玻璃生成失败: {e}")
        return ""

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

def memo_mode() -> str:
    """
    回忆快闪——本地零依赖，一屏看完沙漏记住了什么。
    
    2D 离线（80分）:
      - 画像摘要（persona.md 四层）
      - 影子可视化（shadow_chart）
      - 阶段简报（stage_brief）
      - 最近决策（decision_particles）
    
    3D LLM（200分）:
      - 加一段自然语言总结
    """
    lines = [f"🧬 沙漏画像记忆 — {datetime.now():%Y-%m-%d %H:%M}", ""]
    
    # 画像
    lines.append("【你是谁】")
    if os.path.exists(_PERSONA):
        with open(_PERSONA, "r", encoding="utf-8") as f:
            persona = f.read()
        # 取前两段作为摘要
        sections = [s.strip() for s in persona.split("\n## ") if s.strip()]
        for s in sections[:2]:
            first_line = s.split("\n")[0] if "\n" in s else s[:60]
            lines.append(f"  {first_line[:80]}")
    else:
        lines.append("  （画像尚未生成）")
    lines.append("")
    
    # 影子可视化
    lines.append("【你的影子】")
    try:
        lines.append(shadow_chart())
    except Exception as e:
        logger.warning(f"memo_mode: 影子可视化失败: {e}")
        lines.append("  （数据不足）")
    lines.append("")
    
    # 阶段简报
    lines.append("【当前阶段】")
    try:
        lines.append(stage_brief())
    except Exception as e:
        logger.warning(f"memo_mode: 阶段简报失败: {e}")
        lines.append("  （数据不足）")
    lines.append("")
    
    # 最近决策
    lines.append("【最近决策粒子】")
    dp_path = os.path.join(os.path.expanduser("~"), ".neurobase", "decision_particles.txt")
    if os.path.exists(dp_path):
        with open(dp_path, "r", encoding="utf-8") as f:
            particles = f.readlines()[-5:]
        for p in particles:
            lines.append(f"  {p.strip()[:100]}")
    if len(lines) == 1:
        lines.append("  （决策粒子尚未生成）")
    lines.append("")
    
    # LLM 增强
    if _LLM_KEY:
        try:
            ctx = "\n".join(lines)
            result = _llm(
                "你是记忆展示助手。用户想看沙漏记住了什么。总结一下画像+影子+阶段的关联。一句话，20字以内。",
                ctx[:3000], max_tokens=60)
            if result:
                lines.append(f"💬 {result.strip()}")
        except Exception as e:
            logger.warning(f"memo_mode LLM总结失败: {e}")
    


    return "\n".join(lines)
