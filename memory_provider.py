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
            rebuild_index()
            self._initialized = True
            logger.info("NexSandglass MemoryProvider initialized")

    def system_prompt_block(self) -> str:
        """V2.9.0: 灵魂注入——沙漏→偏移+情绪→最近决策→纪律→待办→上下文。"""
        try:
            from sandglass_vault import count
            from sandglass_think import comprehensive_offset, _current_stage, task_pending
            from sandglass_think import _emotional_entropy, _sentiment_wind
            from discipline import iron_rules_with_counts
            from sandglass_think import session_context

            total = count()
            off = comprehensive_offset()
            stage = _current_stage()
            ent = _emotional_entropy()
            wind = _sentiment_wind()
            # 最近对话锚点（关键词摘要——LLM可据此调sandglass_search查全文）
            ctx = ""
            try:
                import re
                from sandglass_paths import _SANDGLASS
                with open(_SANDGLASS, "r", encoding="utf-8") as f:
                    all_lines = f.readlines()
                # 提取最近用户消息作为话题锚点
                user_msgs = []
                for line in all_lines[-150:]:
                    if " | user | " in line:
                        parts = line.strip().split(" | ", 2)
                        if len(parts) >= 3:
                            msg = parts[2].strip()
                            # 过滤测试数据
                            if re.match(r'^(perf_|_linealign|_signal_|V\d+|_speed_|_perf_|_audit_|_test_|_bench_|_fix_|_v\d|_diag|_cleanup|_p\d|bench_|bench-|\d+$|\[L0-auto\]|第\d+条|第\d+行|AR测试|CR测试)', msg):
                                continue
                            if '测试' in msg[:10] and len(msg) < 20:
                                continue
                            if len(msg) < 4:
                                continue
                            user_msgs.append(msg[:40])  # 截断长消息
                # 去重取最近5条
                seen = set()
                anchors = []
                for m in reversed(user_msgs):
                    if m not in seen and len(m) >= 2:
                        seen.add(m)
                        anchors.append(m)
                    if len(anchors) >= 20:
                        break
                anchors.reverse()
                if anchors:
                    ctx = ""
            except: pass

            # 偏移方向
            dirs = {"frugal": f"省钱({off.get('offset',0):+d}%)",
                    "spend": f"愿投({off.get('offset',0):+d}%)",
                    "drift": f"放弃({off.get('offset',0):+d}%)"}
            off_d = dirs.get(off.get('direction', ''), '平稳')

            # 情绪
            mood = "平稳" if ent < 0.5 else ("波动" if ent < 1.0 else "高熵")

            # 最近决策
            decisions_lines = ""
            try:
                import json, os
                from sandglass_paths import _NB
                dlog = os.path.join(_NB, "persona", "decision-log.jsonl")
                if os.path.exists(dlog):
                    with open(dlog, "r", encoding="utf-8") as f:
                        all_lines = f.readlines()
                    recent = [json.loads(l) for l in all_lines[-10:]]
                    recent = [d for d in recent if d.get("decision")]
                    # 去重 + 取最后3条
                    seen, unique = set(), []
                    for d in reversed(recent):
                        if d["decision"] not in seen:
                            seen.add(d["decision"])
                            unique.append(d)
                        if len(unique) >= 3:
                            break
                    unique.reverse()
                    if unique:
                        decisions_lines = "最近决策\n" + "\n".join(
                            f"{i+1}. {d['decision'][:60]}" for i, d in enumerate(unique[:2])
                        )
            except: pass

            # 待办
            tasks_block = ""
            try:
                from l3_tasks import task_pending
                tp = task_pending()
                if tp:
                    nums = ["1.","2.","3.","4.","5."]
                    tasks_lines = "\n".join(f"{nums[i]} {t['task']}" for i, t in enumerate(tp[:5]))
                    tasks_block = "待办\n" + tasks_lines + "\n" + "\n"
            except: pass

            # 织布机搜索滤镜 — V2.9.5: 因果+矛盾+场景+偏移+情绪统一
            weave_block = ""
            try:
                from weave_l3 import weave_search_filter
                weave_block = weave_search_filter(query)
            except: pass

            # V2.9.7 织线摘要注入（数据门控：<20条三元组不注入）
            thread_block = ""
            try:
                from weavethread import wthread_stats, wthread_weave
                stats = wthread_stats()
                if stats["total_triples"] >= 20:
                    thread_block = wthread_weave(limit=3)
            except: pass



            # 纪律（按提醒次数排序，最多3条）
            rules_lines = ""
            try:
                rules = iron_rules_with_counts(3)
                if rules:
                    # 有计数的显示「×N」，全0的只显示规则文本
                    if any(c > 0 for _, c in rules):
                        rules_lines = "\n".join(f"{i+1}. {r}  ×{c}" for i, (r, c) in enumerate(rules))
                    else:
                        rules_lines = "\n".join(f"{i+1}. {r}" for i, (r, _) in enumerate(rules))
            except: pass

            # 阶段 + 场景语义
            stage_scenes = ""
            doing_lines = ""
            try:
                from scene_l3 import scene_current
                scenes = scene_current()
                if scenes:
                    stage_scenes = " → " + "、".join(scenes[:3])
                    doing_lines = "最近在做\n" + "\n".join(
                        f"{i+1}. {s}" for i, s in enumerate(scenes[:3])
                    )
            except: pass

            note = f"""NexSandglass灵魂注入
纪律
{rules_lines or '尚无纪律——可询问主人是否要设定铁律(如"永远说实话""优先本地方案"等)'}
{weave_block}
{thread_block}
偏移: {off_d} | 情绪: {mood}
{decisions_lines}
{tasks_block}{doing_lines}
阶段: {stage}{stage_scenes} | 沙漏: {total}条"""
            return note.strip()
        except Exception:
            return "NexSandglass记忆系统已就绪。使用sandglass_search搜索记忆。"

    def prefetch(self, query: str) -> str:
        """每轮对话前注入织布机摘要——偏移+情绪+场景。主注入已有全貌，这里只给最动态的信号。"""
        try:
            from sandglass_think import comprehensive_offset, _current_stage, _emotional_entropy
            off = comprehensive_offset()
            ent = _emotional_entropy()
            mood = "平稳" if ent < 0.5 else ("波动" if ent < 1.0 else "高熵")
            dirs = {"frugal": "省钱", "spend": "愿投", "drift": "放弃"}
            off_d = dirs.get(off.get('direction',''), '平稳')
            return (
                f"## 当前\n"
                f"偏移: {off_d}({off.get('offset',0):+d}%) | 情绪: {mood}\n"
            )
        except Exception:
            return ""

    def queue_prefetch(self, query: str) -> None:
        """后台预热——搜索足够快，不需要预热。保持接口兼容。"""
        pass

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
        """会话结束——蒸馏 + 偏移检查。"""
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
