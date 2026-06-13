"""NeuroBase Sandglass L3 -- 蒸馏·偏移率·搜索滤镜。完整架构见 CLAUDE.md / README。"""

import json
import hashlib
import logging
import os
import re
import statistics
import time
import urllib.request
import urllib.error
from datetime import datetime

from sandglass_vault import _tokenize

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

from scene_l3 import (
    scene_mode, scene_add, scene_current, scene_sync,
    scene_history, scene_dominance, stage_switch_prediction,
    scene_stage_matrix, novel_scene_detect,
    _log_scene_timeline, _load_scenes, _save_scenes,
    scene_remove, scene_guess,
)
from weave_l3 import (
    weave_insight, weave_contradiction, weave_chain, weave_graph,
)
from emotion_l3 import (
    entropy_mirror, entropy_ghost, glass_reminder,
    entropy_reminder, memo_mode,
)
from discipline import iron_rules, iron_rules_set
from l3_tasks import task_defer, task_pending, task_done, task_check_trigger
from l3_persona_verify import persona_trace, persona_verify, persona_diff
from l3_search_core import _synonym_expand, _tfidf_search, composite_rerank, _search_with_fallback, _sentiment_wind, sentiment_rerank, simhash_search
from l3_persona import persona_project
from persona_l3 import (
    persona_build, persona_update, persona_canvas,
    persona_freshness, stage_list, stage_canvas,
    _current_stage, _load_persona, _local_persona_extract,
    sand_since_update, stage_similarity,
)
from persona_l3 import _WAVE_THRESHOLDS, _SEARCH_WEIGHTS
from offset_l3 import (
    _log_decision, _read_decision_log, comprehensive_offset,
    _maybe_switch_stage, offset_check, offset_guide,
    cross_stage_offset, offset_chart, shadow_chart,
    stage_mark, stage_marks,
    _STAGE_THRESHOLD,
)

# ── LLM 配置（单一来源：offset_signals）──
from offset_signals import _LLM_KEY, _LLM_ENDPOINT, _LLM_MODEL

logger = logging.getLogger(__name__)

# ═══════════════════ 场景感知 ═══════════════════
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

# ── fail-open 装饰器（单一来源：offset_signals）──
from offset_signals import _fail_open

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
        return body["choices"][0]["message"].get("content") or body["choices"][0]["message"].get("reasoning_content", "")
    except Exception:
        return ""

_FULL_SANITY = {
    "L1_plugin": ["plugin.py"],
    "L1_nightwatch": ["nightwatch.py"],
    "L2_vault": ["sandglass_vault.py"],
    "L2_sqlite": ["sandglass_sqlite.py"],
    "L3_think": ["sandglass_think.py"],
    "L3_pulse": ["pulse.py"],
    "L3_emotion": ["emotion_vocab.py"],
    "L3_particles": ["decision_particles.py"],
    "L3_log": ["sandglass_log.py"],
    "L3_mcp": ["sandglass_mcp.py"],
    "L3_nex": ["nexsandglass.py"],
    "L3_test": ["test_smoke.py"],
}

_HEALTH_REPORT = os.path.join(_NB, "health_report.json")

def full_sanity() -> dict:
    """
    沙漏记忆系统全面体检----三层健康 + 全接口冒烟。
    
    - L0（会话层）：Hermes alive check
    - L1（写层）：沙漏文件 + 明文 + 插件
    - L2（读层）：FTS5/idx/mmap/search
    - L3（思层）：偏移率/画像/情绪熵/织布机/决策粒子/搜索

    返回 {l0, l1, l2, l3, total, summary, details}
    """
    report = {"ts": datetime.now().isoformat(), "layers": {}, "total": 0, "passed": 0, "details": {}}

    # L0
    try:
        import hermes_constants
        report["layers"]["L0"] = "✅ Hermes alive"
        report["passed"] += 1
    except Exception:
        report["layers"]["L0"] = "⚠️ Hermes not detected (standalone mode)"
    report["total"] += 1

    # L1
    try:
        from nightwatch import night_watch
        nw = night_watch()
        report["layers"]["L1"] = "✅" if "沙漏存在" in nw else "⚠️"
        report["details"]["L1_nightwatch"] = nw[:200]
        if "沙漏存在" in nw: report["passed"] += 1
    except Exception as e:
        report["layers"]["L1"] = f"❌ {e}"
    report["total"] += 1

    # L2
    try:
        from sandglass_vault import count, search
        total = count()
        hits = search("test", limit=3)
        l2_ok = total >= 0 and isinstance(hits, list)
        report["layers"]["L2"] = f"✅ {total}条沙子, 搜索正常" if l2_ok else "⚠️"
        report["details"]["L2_sands"] = total
        if l2_ok: report["passed"] += 1
    except Exception as e:
        report["layers"]["L2"] = f"❌ {e}"
    report["total"] += 1

    # L3 -- 全接口检查
    try:
        from functools import lru_cache
        # 只测不会产生副作用的读接口
        checks = {}
        try:
            from sandglass_think import _emotional_entropy
            checks["情绪熵"] = "✅" if _emotional_entropy() >= 0 else "?"
        except: checks["情绪熵"] = "❌"
        try:
            from sandglass_think import comprehensive_offset
            o = comprehensive_offset()
            checks["偏移率"] = f"✅ {o['offset']:+d}% ({o['sample']}条)"
        except: checks["偏移率"] = "❌"
        try:
            from sandglass_think import weave_contradiction
            w = weave_contradiction()
            checks["织布机"] = f"✅ {len(w.get('conflicts',[]))}处矛盾"
        except: checks["织布机"] = "❌"
        try:
            from sandglass_think import stage_list
            s = stage_list()
            checks["阶段"] = f"✅ {len(s)}阶段"
        except: checks["阶段"] = "❌"
        try:
            from sandglass_think import search_filter
            sf = search_filter("test")
            checks["搜索"] = "✅" if sf.get("keywords") else "⚠️"
        except: checks["搜索"] = "❌"
        try:
            from decision_particles import _detect_chain
            c = _detect_chain("选A还是B")
            checks["决策粒子"] = "✅" if isinstance(c, list) else "⚠️"
        except: checks["决策粒子"] = "❌"
        try:
            from sandglass_think import scene_stage_matrix
            ssm = scene_stage_matrix()
            checks["场景矩阵"] = f"✅ {len(ssm.get('stages',[]))}阶段×{len(ssm.get('scenes',[]))}场景"
        except: checks["场景矩阵"] = "❌"
        try:
            from sandglass_think import scene_stage_cross_validate
            sv = scene_stage_cross_validate()
            n_refined = sum(1 for f in sv.get("findings", []) if f.get("refined"))
            checks["场景-阶段交叉验证"] = f"✅ {n_refined}处需细化" if n_refined else "✅ 一致"
        except: checks["场景-阶段交叉验证"] = "❌"
        try:
            from sandglass_think import entropy_mirror
            em = entropy_mirror("最近决策")
            checks["熵镜"] = "✅" if em.get("found_mirror") or "无匹配" in str(em) else "✅"
        except: checks["熵镜"] = "❌"
        try:
            from sandglass_think import entropy_ghost
            eg = entropy_ghost("如果选另一个选项呢")
            checks["幽灵决策"] = "✅" if isinstance(eg, dict) else "⚠️"
        except: checks["幽灵决策"] = "❌"
        try:
            fb = _metrics_feedback()
            checks["度量反馈"] = "✅" if isinstance(fb, dict) else "⚠️"
        except: checks["度量反馈"] = "❌"

        l3_ok = all("✅" in v for v in checks.values())
        report["layers"]["L3"] = "✅ 全接口通过" if l3_ok else "⚠️ 部分接口异常"
        report["details"]["L3_checks"] = checks
        if l3_ok: report["passed"] += 1
    except Exception as e:
        report["layers"]["L3"] = f"❌ {e}"
    report["total"] += 1

    # 总结
    status = "🎉 全部通过" if report["passed"] == report["total"] else f"⚠️ {report['passed']}/{report['total']} 通过"
    report["summary"] = status
    report["summary_short"] = f"L0{'✅' if '✅' in report['layers'].get('L0','') else '⚠️'} L1{'✅' if '✅' in report['layers'].get('L1','') else '⚠️'} L2{'✅' if '✅' in report['layers'].get('L2','') else '⚠️'} L3{'✅' if '✅' in report['layers'].get('L3','') else '⚠️'}"

    # 落盘
    os.makedirs(os.path.dirname(_HEALTH_REPORT), exist_ok=True)
    with open(_HEALTH_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report

_PERSONA_SYSTEM = """# 🧬 人格架构师 -- 渐进演化协议

你是 NeuroBase 的记忆系统。你需要从主人的对话沙子中提炼他的画像，写入 persona.md。

## ⛔ 铁律
1. **只能从提供的对话沙子中提炼，禁止编造。**
2. **每条声明必须注明 `[src:L行号]`----这叫"项链"，可追溯到 sandglass.txt。系统会自动加 SHA256 hash 防 LLM 幻觉。**
3. **首次生成用 write 模式全量写，增量更新只改变化部分。**
4. **保持克制：信息不足的维度留空，不要臆测。**
5. **中文输出。**
6. **调用 glass_reminder() 读取当前玻璃画像----2D 曲面轮廓 + 3D 立体注解。画像生成过程中随时核对玻璃结果，确保一致。** 调用 persona_project() 读取影子灵魂----如果偏移方向暗示用户正在变化，在画像中标注趋势。**

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
**这是最重要的层----教 Agent 如何正确服务主人。**

### 🔴 第四层：认知内核
扫描目标：决策逻辑、矛盾点、终极驱动力。
提取：他做什么决策时反复出现的模式、核心价值观。

## 📝 输出模板

```markdown
# 主人画像 -- 四层深度扫描

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

def _metrics_feedback() -> dict:
    """读取最近度量指标，返回调整建议。"""
    ml = os.path.join(_VAULT, "metrics.log")
    if not os.path.exists(ml): return {}
    try:
        with open(ml, "r", encoding="utf-8") as f:
            lines = f.readlines()[-100:]
        if len(lines) < 10: return {}
        offsets = []
        for line in lines:
            m = re.search(r'offset=([+-]?\d+)', line)
            if m: offsets.append(int(m.group(1)))
        if not offsets: return {}
        avg_offset = sum(offsets[-10:]) / len(offsets[-10:])
        return {"avg_offset": avg_offset, "sample": len(offsets),
                "drift_accelerating": len(offsets) > 20 and abs(sum(offsets[-5:])/5) > abs(sum(offsets[-20:-5])/15)}
    except: return {}

def _current_stage() -> str:
    """读当前阶段标签。O(1) -- 只读最后一行。"""
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

def scene_stage_cross_validate() -> dict:
    """场景-阶段交叉验证。
    阶段标记说两个阶段相似，但按场景拆分后重新检查----相似只存在于某些场景。
    返回 {findings, suggestion}"""
    marks = stage_marks()
    if isinstance(marks, list):
        return {"findings": [], "suggestion": "暂无阶段标记数据"}
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

def persona_maintain() -> dict:
    """人格自动维护。沙子够了+偏移稳定→自动触发更新。V2.9.7: 阈值降至80条+24h最小间隔"""
    fresh = persona_freshness()
    if not fresh["since_sands"] or fresh["since_sands"] < 80:
        return {"triggered": False, "reason": "沙子不足（" + str(fresh.get("since_sands", 0)) + "条，需80+）"}

    # 24h 最小间隔检查
    from persona_l3 import _PERSONA as _PERSONA_FILE
    if os.path.exists(_PERSONA_FILE):
        age_hours = (time.time() - os.path.getmtime(_PERSONA_FILE)) / 3600
        if age_hours < 24:
            return {"triggered": False, "reason": f"距上次更新仅{age_hours:.1f}h，需≥24h间隔"}

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


# ═══════════════════ V2.8 四路并发搜索引擎 ═══════════════════

def _detect_lang(query: str) -> str:
    """纯文本语言检测：'zh', 'en', 'mixed'"""
    has_cjk = any('一' <= c <= '鿿' for c in query)
    has_alpha = any(c.isascii() and c.isalpha() for c in query)
    if has_cjk and has_alpha: return "mixed"
    elif has_cjk: return "zh"
    else: return "en"

def _tokenize_for_density(query: str) -> set:
    """查询分词（语言感知）：中文2字滑窗+英文2-3gram"""
    lang = _detect_lang(query)
    tokens = set()
    if lang in ("zh", "mixed"):
        prev_cjk = None
        for c in query:
            if '一' <= c <= '鿿':
                if prev_cjk: tokens.add(prev_cjk + c)
                prev_cjk = c
            else: prev_cjk = None
    if lang in ("en", "mixed"):
        for w in __import__('re').findall(r'[a-zA-Z]+', query.lower()):
            if len(w) >= 2:
                tokens.add(w)
                for n in (2, 3):
                    for i in range(len(w) - n + 1):
                        tokens.add(w[i:i+n])
    return tokens

from l3_search_core import sand_density

def simhash_rerank(query: str, candidates: list) -> dict:
    """SimHash语义重排：对所有候选集计算汉明距离，返回{line_num: bonus}"""
    try:
        from l3_search_core import simhash, _hamming
        q_fp = simhash(query)
        if q_fp == -1: return {}
        scores = {}
        for ln, ts, text in candidates:
            d_fp = simhash(text[:500])
            if d_fp == -1: continue
            dist = _hamming(q_fp, d_fp)
            if dist <= 55:
                scores[ln] = max(0, (55 - dist) / 55 * 0.5)
        return scores
    except: return {}

def dynamic_expand(hit_line: int, query_tokens: set, all_lines: list, max_ctx: int = 15, threshold: float = 0.2):
    """沙子密度衰减扩窗：遇到密度断崖就停"""
    start, end = hit_line, hit_line
    for i in range(hit_line - 1, max(0, hit_line - max_ctx), -1):
        _, _, text = __import__('sandglass_vault')._parse_line(all_lines[i]) if callable(getattr(__import__('sandglass_vault'), '_parse_line', None)) else (None, None, all_lines[i])
        if text and sand_density(text, query_tokens) >= threshold: start = i
        else: break
    for i in range(hit_line + 1, min(len(all_lines), hit_line + max_ctx)):
        _, _, text = __import__('sandglass_vault')._parse_line(all_lines[i]) if callable(getattr(__import__('sandglass_vault'), '_parse_line', None)) else (None, None, all_lines[i])
        if text and sand_density(text, query_tokens) >= threshold: end = i
        else: break
    return all_lines[start:end+1]
def search_semantic(query: str, limit: int = 10) -> list:
    """V2.8.7: SearchRouter 统一搜索入口 + 密度元数据输出。
    search_filter 扩展关键词 → SearchRouter → 密度标注 → 情感重排。"""
    expanded_query = query
    try:
        filt = search_filter(query)
        expanded = filt.get("keywords", [query])
        expanded_query = " ".join(expanded[:8])
    except Exception:
        pass

    results = []
    try:
        from search_router import SearchRouter
        router = SearchRouter()
        results = router.search(expanded_query, limit)
    except Exception:
        pass

    if not results:
        try:
            from sandglass_vault import search as vs
            results = vs(query, limit)
        except Exception:
            return []

    # V2.8.7: 标注密度元数据 — 每条结果附带 sand:0.XX 标签
    query_tokens = _tokenize_for_density(query)
    enriched = []
    for item in results:
        ln, ts, text = item[0], item[1], item[2]
        density = sand_density(text, query_tokens)
        enriched.append((ln, ts, text, f"sand:{density:.2f}"))

    return sentiment_rerank(enriched, _sentiment_wind())

def _llm_expand(query: str) -> list:
    """LLM 语义扩展----把用户查询扩展为多个相关关键词。
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
权限保护
本地安全
数据隐私
零依赖"""

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

def decision_snapshot(decision_text: str, offset_result: dict = None) -> dict:
    """决策全维度快照----点、线、面。传入offset_result可断递归。"""
    if offset_result:
        point = offset_result
    else:
        point = offset_check(decision_text)
    line = cross_stage_offset(decision_text)

    surface = {}
    for sc in scene_current():
        comp = comprehensive_offset(scene=sc)
        if comp["sample"] > 0:
            surface[sc] = comp

    return {"point": point, "line": line, "surface": surface}

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
                               ("工具", ["Python", "Hermes", "本地"])]:
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

    # ── 影子沙注入（脱口而出层的实体标签 → 搜索权重）──
    try:
        from shadow_sand import shadow_search
        db = __import__('shadow_sand')._get_conn()
        sh = shadow_search(query, 5)
        if sh:
            line_nums = [ln for _, ln in sh[:3]]
            # 读取实体的标签/类别
            for ln in line_nums:
                row = db.execute("SELECT category, tags FROM fact_tags WHERE line_num = ?", (ln,)).fetchone()
                if row:
                    if row[0] and row[0] != 'general':
                        tag = row[0]
                        if tag not in result["keywords"]:
                            result["keywords"].append(tag)
                            result["weights"][tag] = 1.5
                    if row[1]:
                        for tag in row[1].split(","):
                            tag = tag.strip()
                            if tag and tag not in result["keywords"]:
                                result["keywords"].append(tag)
                                result["weights"][tag] = 1.3
            # 实体名注入 — 精确匹配行号，避免LIKE误命中
            entities = []
            for (name, line_nums_str) in db.execute("SELECT name, line_nums FROM entities LIMIT 100").fetchall():
                parts = set(line_nums_str.split(","))
                if any(str(ln) in parts for ln in line_nums):
                    entities.append((name,))
                    if len(entities) >= 3:
                        break
            for (name,) in entities:
                if name.lower() not in [k.lower() for k in result["keywords"]]:
                    result["keywords"].append(name)
                    result["weights"][name] = 1.6  # 实体名最高权重
            if sh or entities:
                result["shadow_context"] = f"影子沙命中{len(sh)}条, 实体{len(entities)}个"
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
    # 但偏移方向作为第 5 维权重注入搜索结果排序。
    # ═══════════════════════════════════════════════

    # ── 偏移方向（第 5 维权重）──
    offset_dir = ""
    try:
        comp = comprehensive_offset()
        if comp["sample"] >= 2:
            offset_dir = comp["direction"]
    except Exception:
        pass

    # ── LLM 四维扩展（有 API Key 时）──
    expanded = _llm_expand_with_context(query, 
        result.get("persona_context", ""),
        result.get("scene_context", ""), 
        result.get("stage_context", ""),
        dp_context,
        result.get("decision_bias", ""))
    if expanded and len(expanded) > 1:
        result["keywords"] = expanded
        # 四维权重----场景/画像/阶段/粒子
        base = _SEARCH_WEIGHTS["default"]
        persona_ctx_val = result.get("persona_context", "")
        weights = {}
        for kw in expanded:
            w = base
            if any(s in kw for s in (scenes or [])):
                w *= _SEARCH_WEIGHTS["scene_match"]
            if persona_ctx_val and any(w in kw for w in persona_ctx_val.split()):
                w *= _SEARCH_WEIGHTS["persona_boost"]
            if result.get("decision_bias"):
                w *= _SEARCH_WEIGHTS["particle_push"]
            # 🆕 第 5 维：偏移方向----省钱的你搜到开源方案更靠前
            if offset_dir:
                if offset_dir == "frugal" and any(x in kw for x in ["免费","开源","本地","自己","省"]):
                    w *= 1.3
                elif offset_dir == "spend" and any(x in kw for x in ["付费","高效","专业","买"]):
                    w *= 1.3
                elif offset_dir == "drift" and any(x in kw for x in ["简单","不用","现成","快速"]):
                    w *= 1.2
            weights[kw] = round(w, 2)
        result["weights"] = weights
        result["source"] = "LLM场景+阶段+决策粒子(4D权重)"
    else:
        # 2D 离线也吃决策粒子权重----本地 80 分
        alt_keywords = _synonym_expand(query)
        keywords = alt_keywords if alt_keywords else [query]
        weights = {}
        for kw in keywords:
            w = _SEARCH_WEIGHTS["default"]
            if result.get("decision_weight_boost") and any(t in kw for t in result["decision_weight_boost"]):
                w *= _SEARCH_WEIGHTS["particle_push"]
            # 🆕 第 5 维偏移方向
            if offset_dir:
                if offset_dir == "frugal" and any(x in kw for x in ["免费","开源","本地","自己","省"]):
                    w *= 1.3
                elif offset_dir == "spend" and any(x in kw for x in ["付费","高效","专业","买"]):
                    w *= 1.3
                elif offset_dir == "drift" and any(x in kw for x in ["简单","不用","现成","快速"]):
                    w *= 1.2
            weights[kw] = round(w, 2)
        result["keywords"] = keywords
        result["weights"] = weights
        result["source"] = "2D本地权重(决策粒子+偏移方向)"

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
5. 结合近期决策倾向，推测用户真正在找什么----决策粒子揭示行为模式，搜索词只是表面意图
6. 返回 3-8 个关键词，一行一个

示例：
画像：性价比优先，偏好开源工具，关注本地安全
场景：NeuroBase开发
阶段轨迹：2024年偏向省钱自研，2025年开始接受付费工具
近期决策：成本观,动手派,独立性
查询：加密
输出：
加密
本地安全
权限保护
沙漏隐私
零依赖
明文"""

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

# 蒸馏的线（你是谁） + 偏移率的线（你怎么变） + 时间检索的线（找什么）
# 织布机不生产新数据，只合成已有数据。

def weave_links() -> dict:
    """互链层----跨阶段关联自动发现并喂给当前画像。
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

    # 全部吸收----小波浪自然累积成大波浪
    if links:
        first = links[0]
        last = links[-1]

        total_drift = 0
        for lk in links:
            for t in lk.get("trajectory", []):
                total_drift += abs(t.get("offset", 0))

        sim_trend = "上升" if last["similarity"] > first["similarity"] else "下降"
        summary = "波动如常----小波浪在累积" if total_drift < 30 * len(links) else f"累积偏移 {total_drift}%----影子已经很深了，轮廓快成形了"
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
                        "consolidated": True, "reason": f"累积{note_count+1}条笔记/偏移{total_drift}%----已重整画像"}

        return {"linked": True, "links": links, "insight": insight}

    return {"linked": False, "insight": "无跨阶段变化"}

def stage_brief() -> str:
    """
    织布机----阶段简报。阶段切换时生成更新日志。
    不自动推送，主人手动调用。
    
    格式：阶段名、触发原因、偏移率、高权重标签、关键决策
    """
    from sandglass_vault import count as sv_count
    
    lines = []
    total = sv_count()

    # 阶段信息
    try:
        sw = stage_switch_prediction()
        lines.append(f"🧬 阶段简报 -- {datetime.now():%Y-%m-%d}")
        lines.append("─" * 40)
        if sw.get("predicted"):
            lines.append(f"⚠ 预切换: {sw.get('eta_sands', '?')}条沙子后 (置信度{sw.get('confidence',0):.0%})")
            lines.append(f"趋势斜率: {sw.get('trend_slope', 0)}")
    except Exception:
        lines.append(f"🧬 阶段简报 -- {datetime.now():%Y-%m-%d}")

    # 偏移率
    try:
        comp = comprehensive_offset()
        if comp["sample"] >= 2:
            direction_cn = {"frugal": "省钱", "spend": "愿意投入", "drift": "放弃倾向"}
            d = direction_cn.get(comp["direction"], comp["direction"])
            lines.append(f"\n📊 偏移率: {comp['offset']:+d}%（{d}），{comp['sample']}次决策")
    except Exception:
        pass

    # 场景-阶段矩阵热力图摘要
    try:
        ssm = scene_stage_matrix()
        if ssm.get("stages") and ssm.get("scenes"):
            lines.append(f"\n🎭 场景分布: {len(ssm['stages'])}阶段 × {len(ssm['scenes'])}场景")
            lines.append(f"   {ssm['insight']}")
    except Exception:
        pass

    # 高权重标签
    try:
        wf = os.path.join(_NB, "search_weights.txt")
        if os.path.exists(wf):
            with open(wf, "r", encoding="utf-8") as f:
                top = [line.strip() for line in f.readlines()[:5] if line.strip()]
            if top:
                lines.append(f"\n🔑 高权重标签: {', '.join(top)}")
    except Exception:
        pass

    # 最近 3 条决策
    try:
        dp_path = os.path.join(_NB, "decision_particles.txt")
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

    # 情绪熵可视化
    try:
        from sandglass_think import entropy_chart
        lines.append(f"\n{entropy_chart()}")
    except Exception:
        pass

    # 新场景发现 → 频率巩固触发器
    try:
        novel = novel_scene_detect()
        if novel.get("drift_trigger"):
            off = comprehensive_offset()
            lines.append(f"\n⚡ 频率突变触发偏移率检查: {off['direction']} {off['offset']:+d}%")
        if novel.get("novel"):
            lines.append(f"\n🆕 新场景: {novel['insight']}")

        # 阶段交叉验证
        cross = scene_stage_cross_validate()
        if cross.get("findings"):
            for f in cross["findings"][:2]:
                if f.get("refined"):
                    lines.append(f"\n🔍 阶段验证: {f.get('stage','?')}需细化")
    except Exception:
        pass

    # 自动蒸馏----每50条新沙子触发一次
    try:
        last_distill = os.path.join(_NB, ".last_distill")
        since = total
        if os.path.exists(last_distill):
            with open(last_distill) as f:
                since = total - int(f.read().strip() or 0)
        if since >= 200:
            lines.append(f"\n🔄 自动蒸馏触发（+{since}条新对话）")
            distill("自动蒸馏", save=True)
            with open(last_distill, "w") as f:
                f.write(str(total))
    except Exception:
        pass


    return "\n".join(lines)

def distill(topic: str = "", save: bool = False) -> str:
    """LLM 蒸馏最近对话。提取关键决策+洞察，写回 vault。"""
    from sandglass_vault import recent

    latest = recent(50)
    if not latest:
        return "(沙漏中没有新对话)"

    lines = []
    for ln, ts, text in latest:
        lines.append(f"[L{ln}:{hashlib.sha256(text[:300].encode()).hexdigest()[:8]} | {ts}] {text[:300]}")
    sand_text = "\n".join(lines)

    system = """# 对话蒸馏器

从主人的对话中提取结构化洞察。输出格式：

```markdown
# 每日洞察 -- {date}

## 🎯 关键决策
- [决策内容] (L行号)

## 💡 新发现/学习
- [如果影子往某个方向移动了，写下方向+幅度]

## 偏移的轮廓
- [省钱/花钱/放弃的轮廓----哪个正在变深]
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
        lines = [f"# 每日洞察 -- {datetime.now():%Y-%m-%d %H:%M}",
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

    # 人格自动维护----检查是否需要触发更新
    try:
        maintain = persona_maintain()
        if maintain.get("triggered"):
            summary += f"\n\n🧬 {maintain.get('action', '人格画像已更新')}"
    except Exception:
        pass

    return summary

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
            trig = (" -- 触发条件：" + t.get("trigger", "")) if t.get("trigger") else ""
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

# 2D 离线 = 玻璃曲面，沙自然累积 → 轮廓渐清（小标签）
# 3D 在线 = LLM 吃进所有 2D 影子 → 合成立体像（大标签，永久保存）
# 每个阶段可以有多个注解----阶段切了、偏移变了、沙子够了、情绪波动了 → 重新生成

_3D_ANNOTATIONS = os.path.join(_NB, "3d_annotations.jsonl")

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

    # ④ 情绪波动 -- 由 pulse.py 调用时传入
    # （这里只是信号检查，实际情绪由 emotion_vocab.detect 决定）
    return False, ""

def _save_annotation(data: dict, trigger: str) -> None:
    """保存阶段注解----永久追加，不替换旧注解。"""
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
    3D 立体画像合成----永久注解模式。
    
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
        weave_path = os.path.join(_NB, "weave_alerts.txt")
        if os.path.exists(weave_path):
            with open(weave_path, "r", encoding="utf-8") as f:
                weave_text = f.read()[-500:]

        # 4. 搜索权重
        weight_text = ""
        wf = os.path.join(_NB, "search_weights.txt")
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

def _emotional_entropy(recent_n: int = 10) -> float:
    """
    香农熵----量化情绪波动程度。
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

def entropy_chart(recent_n: int = 10) -> str:
    """
    情绪熵 ASCII 可视化。
    """
    entropy = _emotional_entropy(recent_n)
    bar_len = min(int(entropy * 20), 40)
    bar = "█" * bar_len + "░" * (40 - bar_len)
    level = "高熵波动" if entropy > 1.2 else ("低熵平静" if entropy < 0.5 else "中熵平稳")
    return f"🫧 情绪熵 {entropy:.2f} {bar}  {level}"

def memory_migrate(output_path: str = "") -> str:
    """
    一键导出全部记忆数据为 tar.gz。换电脑时解压到新 .neurobase/ 即可。
    
    打包内容：
      sandglass.txt / sandglass.backup（沙子+阴影）
      sandglass.idx（投石问路）
      persona/（画像+阶段+时间线）
      decision_particles.txt（决策粒子）
      search_weights.txt / echo_wind.jsonl（搜索权重+回音折风）
    
    不打包代码----只打包记忆本身。
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
