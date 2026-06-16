"""
NexSandglass MemoryProvider — MemoryProvider for Hermes
========================================================
让 Hermes 使用 NexSandglass 作为记忆后端，替代 Holographic。

零API Key、零外部依赖——纯本地驱动。投石问路（倒排索引）优先、
五维权重排序、偏移率感知、回音折情绪追踪、影子灵魂预测。
"""
from __future__ import annotations

import json, logging, os, re, threading, time
from typing import Any, Dict, List, Optional

# 条件导入——兼容赫姆斯环境和独立运行时
try:
    from agent.memory_provider import MemoryProvider
except ImportError:
    class MemoryProvider:
        name = "nexsandglass"
        def is_available(self): return True
        def initialize(self): pass
        def shutdown(self): pass
        def get_tool_schemas(self): return []
        def handle_tool_call(self, name, args): return ""
        def system_prompt_block(self): return ""
        def prefetch(self, query): return None
        def sync_turn(self, user_msg, assistant_msg): pass

try:
    from tools.registry import tool_error
except ImportError:
    def tool_error(msg): return json.dumps({"error": msg})

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# 工具方法——把 sandglass 函数暴露给 Hermes 模型调用
# ══════════════════════════════════════════════════════════

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "sandglass_search",
            "description": "搜索沙漏记忆——投石问路（倒排索引）优先，五维权重排序。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_semantic",
            "description": "精炼语义搜索——六维滤镜+影子沙+同义词+情感重排。概念查询更准。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_migrate",
            "description": "一键导出全部记忆数据为 tar.gz。换电脑时解压即用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "output": {"type": "string", "description": "输出路径", "default": ""},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_export",
            "description": "导出沙漏为可迁移文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "output_path": {"type": "string", "description": "输出路径"},
                    "limit": {"type": "integer", "description": "导出条数"},
                    "month": {"type": "string", "description": "指定月份 YYYY-MM"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_recent",
            "description": "获取最近 N 条记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_offset",
            "description": "计算当前偏移率——主人决策方向的趋势。返回偏移百分比和方向。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fact_store",
            "description": "影子沙事实存储。action=add/search/probe/reason。存储结构化事实，信任评分排序。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "search", "probe", "reason"]},
                    "content": {"type": "string", "description": "事实内容"},
                    "category": {"type": "string", "default": "general"},
                    "query": {"type": "string"},
                    "entity": {"type": "string"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fact_feedback",
            "description": "信任评分反馈。标记记忆是否有帮助。",
            "parameters": {
                "type": "object",
                "properties": {
                    "line_num": {"type": "integer"},
                    "helpful": {"type": "boolean"},
                },
                "required": ["line_num", "helpful"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandglass_echo",
            "description": "读取回音折——最近的情感风向。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class NexSandglassProvider(MemoryProvider):
    """NexSandglass 记忆提供器——替代 Holographic，纯本地零依赖。"""

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._lock = threading.Lock()
        self._initialized = False
        self._turn_count = 0

    # ═══════ MemoryProvider 核心接口 ═══════

    @property
    def name(self) -> str:
        return "nexsandglass"

    def is_available(self) -> bool:
        """始终可用——零API Key，纯本地。"""
        return True

    def initialize(self, session_id: str = "", **kwargs) -> None:
        """设置沙漏路径、重建投石问路索引。"""
        with self._lock:
            if self._initialized:
                return
            # 确保 sandglass 模块可导入
            import sys
            nb = os.environ.get("NEXSANDBASE_HOME") or os.path.expanduser("~/.neurobase")
            nb_scripts = os.path.join(nb, "scripts")
            if nb_scripts not in sys.path:
                sys.path.insert(0, nb_scripts)

            from sandglass_vault import rebuild_index
            from sandglass_paths import validate
            validate()
            # V2.9.37: 索引重建仅首次运行
            idx_done = os.path.join(nb, "idx_done")
            if not os.path.exists(idx_done):
                rebuild_index()
                with open(idx_done, "w") as f: f.write("1")
            # V2.9.39: DB自省增量——用trust表MAX(line_num)替代外部checkpoint
            try:
                import sqlite3
                sand_path = os.path.join(nb, "sandglass.txt")
                if os.path.exists(sand_path):
                    current_lines = sum(1 for _ in open(sand_path, encoding="utf-8", errors="replace"))
                    db = sqlite3.connect(os.path.join(nb, "shadow_sand.db"))
                    max_trust = db.execute("SELECT COALESCE(MAX(line_num), 0) FROM trust").fetchone()[0]
                    db.close()
                    if current_lines > max_trust:
                        from shadow_sand import shadow_index
                        with open(sand_path, encoding="utf-8", errors="replace") as f:
                            for ln, line in enumerate(f, 1):
                                if ln <= max_trust: continue
                                text = line.strip()
                                if text: shadow_index(text, line_num=ln)
            except Exception as e:
                logger.warning(f"增量初始化跳过: {e}")
            self._initialized = True
            logger.info("NexSandglass V2.9.37 就绪")

    def system_prompt_block(self) -> str:
        """V2.9.8: 四层问答式注入 — 你是谁→往哪走→怎么变成这样→还没做完"""
        try:
            from sandglass_vault import count
            from sandglass_think import comprehensive_offset, _current_stage
            from sandglass_think import _emotional_entropy, search_filter

            total = count()
            off = comprehensive_offset()
            stage = _current_stage()
            ent = _emotional_entropy()
            mood = "平稳" if ent < 0.5 else ("波动" if ent < 1.0 else "高熵")

            # 偏移方向
            dirs = {"frugal": "省钱", "spend": "愿投", "drift": "放弃"}
            off_label = dirs.get(off.get('direction', ''), '平稳')
            off_pct = off.get('offset', 0)

            blocks = []

            # ═══════ 第一层：你是谁 V2.9.9.10 数据点 ═══════
            identity_parts = []
            
            # 身份：从画像快照提取
            try:
                from persona_l3 import _local_persona_extract
                local = _local_persona_extract()
                if local and local != "数据不足":
                    for line in local.split("\n"):
                        if "：" in line or ":" in line:
                            identity_parts.append(line.strip()[:60])
            except Exception: pass
            
            # 铁律：从 five-facets.json 注入结构化事实（importance×confidence 排序）
            try:
                import json
                facets_path = os.path.join(_NB, "profile", "five-facets.json")
                if os.path.exists(facets_path):
                    with open(facets_path, "r", encoding="utf-8") as f:
                        facets = json.load(f)
                    all_entries = []
                    for facet_name in ["fact","preference","restriction","task_pattern","style"]:
                        for entry in facets.get(facet_name, []):
                            imp = entry.get("importance", 0)
                            conf = entry.get("confidence", 0)
                            all_entries.append((imp * conf, entry["content"]))
                    all_entries.sort(reverse=True)
                    for _, content in all_entries[:5]:
                        # V2.9.28: 极简注入→只取标题（"："前的部分）
                        title = content.split("：")[0].split(":")[0].split("=")[0].strip()[:20]
                        if title and title not in identity_parts:
                            identity_parts.append(title)
            except Exception: pass
            
            # 决策：管道洞察已含偏移方向，此处不重复
            
            # 关注：从fact_tags高频标签
            try:
                import sqlite3, os
                from collections import Counter
                db = sqlite3.connect(os.path.join(_NB, "shadow_sand.db"))
                tags = Counter()
                for r in db.execute("SELECT tags FROM fact_tags WHERE tags != '' AND tags != '未分类'").fetchall():
                    for t in r[0].split(","):
                        t = t.strip()
                        if t and len(t) > 1: tags[t] += 1
                db.close()
                top = [t for t,_ in tags.most_common(3) if _ >= 2]
                if top: identity_parts.append(f"关注: {', '.join(top)}")
            except Exception: pass
            
            # 场景
            scene_text = ""
            try:
                from scene_l3 import scene_current
                scenes = scene_current()
                if scenes: scene_text = ", ".join(scenes[:3])
            except Exception: pass
            
            if not identity_parts:
                identity_parts.append("身份: 待积累（使用中自动发现）")
            
            blocks.append(f"【你是谁】\n{' | '.join(identity_parts)}")
            if scene_text:
                blocks.append(f"📍 {scene_text}")

            # V2.9.9.7: 溯源异常告警
            try:
                from l3_persona_verify import persona_verify
                pv = persona_verify()
                if pv.get("failed", 0) > 0:
                    blocks.append(f"⚠️ 画像溯源异常：{pv['failed']}条声明源行已变更")
            except Exception:
                pass

            # ═══════ 第二层：你在往哪走（极简） ═══════
            layer2 = []
            # 情绪状态
            if mood != "平稳":
                layer2.append(f"【状态】🎭 {mood}")
            # 最近决策（管道洞察已含，此处只补情绪）
            decisions = []
            try:
                import json, os
                from sandglass_paths import _NB
                dlog = os.path.join(_NB, "persona", "decision-log.jsonl")
                if os.path.exists(dlog):
                    with open(dlog, "r", encoding="utf-8") as f:
                        all_lines = f.readlines()
                    recent = [json.loads(l) for l in all_lines[-10:]]
                    recent = [d for d in recent if d.get("decision")]
                    seen_d, unique_d = set(), []
                    for d in reversed(recent):
                        if d["decision"] not in seen_d:
                            seen_d.add(d["decision"])
                            unique_d.append(d)
                        if len(unique_d) >= 2:
                            break
                    unique_d.reverse()
                    decisions = [d['decision'][:60] for d in unique_d]
                    # 子串去重：短的被长的包含→去掉短的
                    if len(decisions) == 2 and decisions[0] in decisions[1]:
                        decisions = [decisions[1]]
                    elif len(decisions) == 2 and decisions[1] in decisions[0]:
                        decisions = [decisions[0]]
            except Exception:
                pass
            if decisions:
                layer2.append(f"📋 最近：{'；'.join(decisions)}")

            # V2.9.9.7: 情绪×偏移预判+语气合并行
            try:
                from offset_l3 import psychology_hint
                hint = psychology_hint()
                emo = ""
                if mood != "平稳":
                    tone = ""
                    if ent > 1.0: tone = " — 安静陪着"
                    elif ent < 0.3: tone = " — 状态稳"
                    emo = f" 🎭 {mood}{tone}"
                elif ent < 0.3:
                    emo = " 🎭 平稳 — 状态稳"
                if hint or emo:
                    line = (hint or "") + emo
                    if line.strip():
                        layer2.append(line.strip())
            except Exception:
                pass

            # 矛盾检测
            try:
                from weave_l3 import weave_contradiction
                contra = weave_contradiction()
                if contra.get("conflicts"):
                    c0 = contra["conflicts"][0]
                    if c0.get("conflict"):
                        layer2.append(f"⚠️ {c0['conflict'][:100]}")
            except Exception:
                logger.debug("矛盾检测失败", exc_info=True)


            blocks.append("\n".join(layer2))

            # ═══════ 第三层：你怎么变成这样 ═══════
            try:
                from weavethread import wthread_stats, wthread_weave
                stats = wthread_stats()
                if stats["total_triples"] >= 20:
                    thread = wthread_weave(limit=3)
                    if thread and thread != "织线因果:":
                        blocks.append(f"【你怎么变成这样】\n{thread[:200]}")
            except Exception:
                logger.debug("织线失败", exc_info=True)

            # ═══════ 第四层：还没做完 ═══════
            layer4 = []

            # 待办
            tasks = []
            try:
                from l3_tasks import task_pending
                tp = task_pending()
                if tp:
                    tasks = [t['task'][:80] for t in tp[:3]]
            except Exception:
                pass

            # 铁律
            rules = []
            try:
                from discipline import iron_rules_with_counts, iron_rule_inject_bump
                raw_rules = iron_rules_with_counts(3)
                if raw_rules:
                    if any(c > 0 for _, c in raw_rules):
                        rules = [f"{r} ×{c}" for r, c in raw_rules]
                    else:
                        rules = [r for r, _ in raw_rules]
                    # V2.9.9: 会话级去重bump — 每条规则每session+1
                    for r, _ in raw_rules:
                        iron_rule_inject_bump(r)
            except Exception:
                pass

            if tasks or rules:
                header = "【还没做完】"
                if tasks:
                    layer4.append(header)
                    layer4.append("待办：")
                    layer4.extend(f"  {i+1}. {t}" for i, t in enumerate(tasks))
                if rules:
                    if not tasks:
                        layer4.append(header)
                    layer4.append("铁律：")
                    layer4.extend(f"  {i+1}. {r}" for i, r in enumerate(rules))
                blocks.append("\n".join(layer4))

            # ═══════ 管道洞察（V2.9.11） ═══════
            try:
                from sandglass_think import _synthesize_3d
                syn = _synthesize_3d(trigger="inject")
                if syn and syn.get("pipe_insights"):
                    blocks.append(f"🔍 {syn['pipe_insights']}")
            except Exception: pass

            # ═══════ 尾部 ═══════
            blocks.append(f"沙漏: {total}条 | 阶段: {stage}")

            return "\n\n".join(blocks).strip()
        except Exception:
            logger.warning("system_prompt_block 整体失败", exc_info=True)
            return "NexSandglass记忆系统已就绪。使用sandglass_search搜索记忆。"

    def prefetch(self, query: str) -> str:
        """V2.10.7: 三块式轮次注入 — 搜索引导+记忆预览(带精搜引导)+状态决策。~150t。"""
        try:
            blocks = []
            hints = getattr(self, '_prefetch_hints', [])
            
            # ═══ 块1: 搜索引导 (~40t) ═══
            guide = []
            if hints:
                guide.append(f"搜索: {' / '.join(hints[:3])}")
            try:
                import sqlite3, os
                from sandglass_paths import _NB
                db = sqlite3.connect(os.path.join(_NB, "shadow_sand.db"))
                tags_set = set()
                for r in db.execute("SELECT category, tags FROM fact_tags WHERE tags!='' ORDER BY rowid DESC LIMIT 10").fetchall():
                    if r[1]:
                        for t in r[1].split(",")[:2]:
                            t = t.strip()
                            if len(t) > 1: tags_set.add(t[:12])
                db.close()
                if tags_set: guide.append(f"标签: {', '.join(list(tags_set)[:4])}")
            except: pass
            try:
                from scene_l3 import scene_current
                sc = scene_current()
                if sc: guide.append(f"📍 {'·'.join(sc[:2])}")
            except: pass
            if guide: blocks.append(" | ".join(guide))
            
            # ═══ 块2: 记忆预览 (~70t) — 带精搜引导 ═══
            try:
                from search_router import SearchRouter
                sr = SearchRouter()
                search_q = " ".join(hints[:3]) if hints and len(hints) > 1 else query
                results = sr.search(search_q, limit=3)
                if results:
                    mem_lines = []
                    for i, (ln, ts, text) in enumerate(results[:3]):
                        prefix = "✓" if i == 0 else "·"
                        t = text[:70].replace("\n", " ")
                        mem_lines.append(f"  {prefix} [{ts[:10]}] {t}")
                    blocks.append("📋 记忆预览:\n" + "\n".join(mem_lines) + "\n  → sandglass_search 可扩展更多")
            except: pass
            
            # ═══ 块3: 状态+决策 (~40t) ═══
            from sandglass_think import comprehensive_offset, _emotional_entropy, _synthesize_3d
            off = comprehensive_offset()
            ent = _emotional_entropy()
            mood = "平稳" if ent < 0.5 else ("波动" if ent < 1.0 else "高熵")
            dirs = {"frugal": "省钱", "spend": "愿投", "drift": "放弃"}
            off_d = dirs.get(off.get('direction',''), '平稳')
            syn = _synthesize_3d(trigger="prefetch")
            pi = syn.get("pipe_insights", "")
            tangle = ""
            if "纠结:" in pi: tangle = " 纠结:" + pi.split("纠结:")[1].split("|")[0].strip()
            lines = [f"状态: {off_d}({off.get('offset',0):+d}%) | 🎭{mood}{tangle}"]
            # 铁律
            try:
                from discipline import iron_rules_with_counts
                rules = iron_rules_with_counts(2)
                if rules: lines.append("⚠" + " ⚠".join(r[:30] for r,_ in rules[:2]))
            except: pass
            # 决策粒子
            try:
                import os
                dp_path = os.path.join(os.environ.get("NEXSANDBASE_HOME", os.path.expanduser("~/.neurobase")), "decision_particles.txt")
                if os.path.exists(dp_path):
                    with open(dp_path, "r", encoding="utf-8", errors="replace") as f:
                        dps = [l for l in f if l.strip() and not l.startswith("#")]
                    if dps:
                        last = dps[-1]
                        if "→" in last:
                            parts = last.split(" | ")
                            if len(parts) >= 4: lines.append(f"决策: {parts[2][:35]} ({parts[3].strip()[:10]})")
            except: pass
            # 洞察精简
            if pi:
                snippets = [s.strip() for s in pi.split("|") if s.strip()]
                key = [s[:40] for s in snippets if any(k in s for k in ["标签:", "告警:", "链:"])]
                if key: lines.append(" | ".join(key[:2]))
            blocks.append("\n".join(lines))
            
            result = "\n\n".join(blocks)
            return result[:700]  # 硬截断
        except Exception:
            return ""

    def queue_prefetch(self, query: str) -> None:
        """后台预热——语义扩展+标签提取。激励LLM主动调sandglass_search。"""
        try:
            from sandglass_think import _infer_expand_with_context, search_filter
            sf = search_filter(query)
            ctx = sf or {}
            expanded = _infer_expand_with_context(
                query,
                ctx.get("persona_context", ""),
                ctx.get("scene_context", ""),
                ctx.get("stage_context", ""),
                ctx.get("dp_context", ""),
                ctx.get("decision_bias", "")
            )
            self._prefetch_hints = expanded[1:5] if expanded and len(expanded) > 1 else []
        except Exception:
            self._prefetch_hints = []

    def sync_turn(self, user_msg: str, assistant_msg: str, **kwargs) -> None:
        """每轮对话后落沙。"""
        try:
            from sandglass_log import log_message
            if user_msg:
                log_message(user_msg, "user")
            if assistant_msg:
                log_message(assistant_msg, "agent")
            self._turn_count += 1
        except Exception:
            pass

    def shutdown(self) -> None:
        """清理。"""
        logger.info("NexSandglass MemoryProvider shutdown")

    # ═══════ fact_store / fact_feedback ═══════

    def _handle_fact_store(self, args: dict) -> str:
        try:
            from sandglass_vault import search as vault_search
            from shadow_sand import shadow_search as _ss, shadow_feedback
            action = args.get("action", "search")

            if action == "add":
                from sandglass_log import log_message
                content = args.get("content", "")
                category = args.get("category", "general")
                log_message(content, "fact_store")
                return json.dumps({"status": "added", "content": content[:100]})

            if action == "search":
                query = args.get("query", "")
                results = vault_search(query, limit=10)
                shadow_hits = _ss(query, limit=10)
                return json.dumps({
                    "fts_results": [{"line": ln, "text": txt[:200]} for ln, _, txt in results],
                    "shadow_boosted": [{"line": ln, "trust": score} for score, ln in shadow_hits],
                }, ensure_ascii=False)

            if action == "probe":
                entity = args.get("entity", "")
                results = _ss(entity, limit=20)
                return json.dumps([{"line": ln, "trust": score} for score, ln in results], ensure_ascii=False)

            if action == "reason":
                entity = args.get("entity", "")
                results = _ss(entity, limit=5)
                if results:
                    ln = results[0][1]
                    from sandglass_vault import search as vs
                    r = vs(str(ln), limit=1)
                    if r:
                        return json.dumps({"line": ln, "text": r[0][2][:300]}, ensure_ascii=False)
                return json.dumps({"status": "no results"})

            return tool_error(f"Unknown fact_store action: {action}")
        except Exception as e:
            return tool_error(f"fact_store error: {e}")

    def _handle_fact_feedback(self, args: dict) -> str:
        try:
            from shadow_sand import shadow_feedback
            result = shadow_feedback(args["line_num"], args.get("helpful", True))
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return tool_error(f"fact_feedback error: {e}")

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """会话结束——落沙 + 偏移检查 + V2.9.9.1情绪摘要。"""
        try:
            # 落最后一轮对话
            for msg in messages[-5:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    from sandglass_log import log_message
                    log_message(str(content)[:500], role)

            # 触发偏移检查 + 织造
            from sandglass_think import comprehensive_offset
            off = comprehensive_offset()
            if abs(off.get("offset", 0)) >= 30:
                logger.info(f"会话结束偏移: {off['offset']:+d}% ({off['direction']})")

            # V2.9.9.1: 情绪会话摘要
            try:
                from emotion_vocab import detect as emotion_detect
                from sandglass_paths import _NB
                import os, json
                mood_counts = {}
                for msg in messages:
                    if msg.get("role") == "user":
                        det = emotion_detect(msg.get("content", ""))
                        mood = det.get("mood", "")
                        if mood:
                            mood_counts[mood] = mood_counts.get(mood, 0) + 1
                if mood_counts:
                    total = sum(mood_counts.values())
                    entry = {
                        "ts": __import__("datetime").datetime.now().isoformat(),
                        "dominant": max(mood_counts, key=mood_counts.get),
                        "distribution": {k: round(v/total, 2) for k, v in mood_counts.items()},
                    }
                    emo_path = os.path.join(_NB, "emotion_session.jsonl")
                    with open(emo_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass

        except Exception:
            pass

    # ═══════ 工具暴露 ═══════

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return _TOOL_SCHEMAS

    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        try:
            if name == "sandglass_search":
                from sandglass_vault import search
                results = search(args.get("query", ""), limit=args.get("limit", 10))
                return json.dumps(
                    [{"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in results],
                    ensure_ascii=False,
                )

            if name == "sandglass_semantic":
                from sandglass_think import search_semantic
                results = search_semantic(args.get("query", ""), limit=args.get("limit", 5))
                return json.dumps(
                    [{"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in results],
                    ensure_ascii=False,
                )

            if name == "sandglass_recent":
                from sandglass_vault import recent
                results = recent(args.get("n", 10))
                return json.dumps(
                    [{"line": ln, "ts": ts, "text": txt[:200]} for ln, ts, txt in results],
                    ensure_ascii=False,
                )

            if name == "sandglass_offset":
                from sandglass_think import comprehensive_offset
                off = comprehensive_offset()
                return json.dumps(off, ensure_ascii=False)

            if name == "sandglass_echo":
                from sandglass_think import _sentiment_wind
                wind = _sentiment_wind()
                return json.dumps({"wind": wind, "direction": "正面" if wind > 0 else ("负面" if wind < 0 else "中性")}, ensure_ascii=False)

            if name == "fact_store":
                return self._handle_fact_store(args)

            if name == "fact_feedback":
                return self._handle_fact_feedback(args)

            return tool_error(f"Unknown NexSandglass tool: {name}")

        except Exception as e:
            return tool_error(f"NexSandglass error: {e}")

    # ═══════ 可选钩子 ═══════

    def on_memory_write(self, action: str, target: str, content: str, metadata: dict = None) -> None:
        """镜像内置记忆写入——同步落沙。"""
        try:
            from sandglass_log import log_message
            text = f"[{action}] {target}: {content[:200]}"
            log_message(text, "memory_write")
        except Exception:
            pass

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """上下文压缩前提取关键记忆。"""
        try:
            from sandglass_vault import search as vs
            # 提取最后一轮对话的关键词搜索
            if messages:
                last = messages[-1].get("content", "")[:100]
                if last:
                    results = vs(last, limit=3)
                    return "\n".join(txt[:200] for _, _, txt in results)
        except Exception:
            pass
        return None


# ── 插件自动发现入口 ──
def register(ctx) -> None:
    """Hermes 插件加载入口——接收 config 上下文并注册 Provider。"""
    provider = NexSandglassProvider()
    ctx.register_memory_provider(provider)
