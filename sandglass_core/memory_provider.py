"""
NexSandglass MemoryProvider — 核心下沉版（熔炼任务 B）
========================================================
让任意 agent 使用 NexSandglass 作为记忆后端，替代 Holographic。

本文件是沙漏唯一核心实现：NexSandglassProvider、工具 schema、
system_prompt_block 组装、prefetch/queue_prefetch、落沙钩子、计数。
agent 适配层（Hermes 的 __init__.py / plugin.py）只做路径准备与注册转发，
不得再出现第二份 NexSandglassProvider。

零API Key、零外部依赖——纯本地驱动。投石问路（倒排索引）优先、
五维权重排序、偏移率感知、回音折情绪追踪、影子灵魂预测。
"""
from __future__ import annotations

import collections, hashlib, json, logging, os, re, threading, time
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

# 版本号由主人最终确认，熔炼迭代禁止自行 bump。
__version__ = "3.1.0"

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
        # V2.20.3: 阶段一——注入块内容hash缓存 + prefetch 3轮去重（纯内存，跨会话重置）
        self._session_id = ""
        self._inject_cached_hash: Optional[str] = None
        self._inject_cached_text: Optional[str] = None
        self._prefetch_query_history: Any = collections.deque(maxlen=3)
        self._queue_prefetch_query_history: Any = collections.deque(maxlen=3)
        self._prefetch_last_text: str = ""
        self._prefetch_hints: list = []
        self._last_rule_context: str = ""

    # ═══════ V2.20.3 阶段一：token 优化——注入缓存 + prefetch 去重 ═══════

    def _reset_stage1_cache(self) -> None:
        """V2.20.3: 清空阶段一内存缓存（注入块hash缓存 + prefetch 3轮去重）。须在持锁下调用。"""
        self._inject_cached_hash = None
        self._inject_cached_text = None
        self._prefetch_query_history.clear()
        self._queue_prefetch_query_history.clear()
        self._prefetch_last_text = ""
        self._last_rule_context = ""
        # V2.20.5: 连同 prefetch 生成的 hints 一起清理，避免跨会话残留
        if getattr(self, "_prefetch_hints", None):
            self._prefetch_hints.clear()

    @staticmethod
    def _normalize_query(query: str) -> str:
        """V2.20.3: prefetch去重用——空白/大小写归一。失败返回空串（不去重）。"""
        try:
            return " ".join(str(query or "").strip().lower().split())
        except Exception:
            return ""

    @staticmethod
    def _query_similar(a: str, b: str) -> bool:
        """V2.20.3: 保守近似判定——精确相等 / 包含 / 显著token重叠。"""
        try:
            if not a or not b:
                return False
            if a == b:
                return True
            if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
                return True
            ta, tb = set(a.split()), set(b.split())
            if ta and tb:
                return len(ta & tb) / min(len(ta), len(tb)) >= 0.6
            return False
        except Exception:
            return False

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
            # V2.20.3: 跨会话重置——session_id 变化时清空阶段一缓存（同一实例复用场景）
            if session_id and session_id != self._session_id:
                self._reset_stage1_cache()
                self._session_id = session_id
            if self._initialized:
                return
            # 确保 sandglass 模块可导入
            import sys
            # 本文件现已位于 sandglass_core/ 内，直接把自身目录加入 sys.path，
            # 保证 from sandglass_* import ... 能命中同目录核心模块。
            _NB_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
            if _NB_SCRIPTS not in sys.path:
                sys.path.insert(0, _NB_SCRIPTS)

            # V2.20.2: 统一路径解析——复用 sandglass_paths.get_nb()（环境变量→config.yaml→默认），
            # 不再手算 fallback，避免与 sandglass_paths 解析不一致而读到 ~/.neurobase 空壳
            from sandglass_paths import get_nb
            _NB_DATA = get_nb()

            from sandglass_vault import rebuild_index
            from sandglass_paths import validate
            validate()
            rebuild_index()
            # V2.9.21: 回填空tags（重启时一次性执行）
            try:
                import sqlite3, re
                db = sqlite3.connect(os.path.join(_NB_DATA, "shadow_sand.db"))
                rows = db.execute("SELECT rowid, line_num FROM fact_tags WHERE tags='' OR tags IS NULL").fetchall()
                if rows:
                    sand_path = os.path.join(_NB_DATA, "sandglass.txt")
                    if os.path.exists(sand_path):
                        with open(sand_path, "r", encoding="utf-8", errors="replace") as sf:
                            sand_lines = sf.readlines()
                        for rid, ln in rows:
                            if 0 < ln <= len(sand_lines):
                                text = sand_lines[ln - 1]
                                # V2.20.4: 统一提取器——与 shadow_index 同源（停用词/长度/ASCII/别名归一化）
                                try:
                                    from shadow_sand import extract_tags
                                    entities = extract_tags(text)
                                except Exception:
                                    logger.warning(f"initialize: 局部导入失败: from shadow_sand import extract_tags", exc_info=True)
                                    ENTITY_RE = re.compile(r'(?:[A-Z][a-z]{2,}(?:[A-Z][a-z]{2,})+|[A-Z]{2,}|[A-Z][a-z]+(?:[ -][A-Z][a-z]+)*|[\u4e00-\u9fff]{2,6})')
                                    entities = [m.group().strip() for m in ENTITY_RE.finditer(text) if len(m.group().strip()) > 1]
                                if entities:
                                    db.execute("UPDATE fact_tags SET tags=? WHERE rowid=?", (",".join(entities[:10]), rid))
                        db.commit()
                db.close()
            except Exception:
                logger.warning("initialize 回填空tags失败", exc_info=True)
            self._initialized = True
            try:
                from sandglass_paths import __version__ as _ver
            except Exception:
                logger.warning(f"initialize: 局部导入失败: from sandglass_paths import __version__ as _ver", exc_info=True)
                _ver = "3.1.0"
            logger.info(f"NexSandglass V{_ver} 就绪")

    def _build_explicit_memory_block(self) -> tuple[str, set[str]]:
        """冲突6：显式记忆块——回溯 _SANDGLASS 最近 200 行中的 memory_write。

        只取 `[action] target: content` 可解析行；按 (action, target, content)
        去重并保留最近 10 条；content 截断约 60 字符。返回 (块文本, seen_facts)。
        """
        try:
            from sandglass_paths import _SANDGLASS
            if not os.path.exists(_SANDGLASS):
                return "", set()
            with open(_SANDGLASS, "r", encoding="utf-8", errors="replace") as f:
                tail = collections.deque(f, maxlen=200)
            parsed = []
            for line in tail:
                if " | memory_write | " not in line:
                    continue
                parts = line.split("|", 2)
                if len(parts) < 3:
                    continue
                payload = parts[2].strip()
                m = re.match(r'^\[([^\]]+)\]\s*(.*?)\s*[:：]\s*(.*)$', payload)
                if not m:
                    continue
                action = m.group(1).strip()
                target = m.group(2).strip()
                content = m.group(3).strip()
                if not content:
                    continue
                parsed.append((action, target, content))
            seen = set()
            ordered = []
            for action, target, content in reversed(parsed):
                key = (action, target, content)
                if key in seen:
                    continue
                seen.add(key)
                ordered.append((action, target, content))
            ordered.reverse()
            ordered = ordered[-10:]
            if not ordered:
                return "", set()
            lines = []
            facts = set()
            for idx, (action, target, content) in enumerate(ordered, 1):
                short = content[:60]
                lines.append(f"  {idx}. [{action}] {target or '?'}: {short}")
                if target:
                    facts.add(target)
                facts.add(short)
            return "\n".join(lines), facts
        except Exception:
            logger.warning("_build_explicit_memory_block 失败", exc_info=True)
            return "", set()

    def _build_entity_block(self, seen_facts: set, token_budget: int = None) -> str:
        """冲突6：高信实体块——过织布机加工层，关联场景上下文。

        数字/单字/已见实体过滤保留在 weave_l3.weave_entities_with_context；
        token_budget 用于三块合计 ≤250 token 的预算截断。
        """
        try:
            from weave_l3 import weave_entities_with_context
            lines = weave_entities_with_context(
                limit=5, seen_facts=seen_facts, max_tokens=token_budget
            )
            for line in lines:
                name = line.split(" (场景:", 1)[0].strip()
                if name:
                    seen_facts.add(name)
            return "\n".join(lines)
        except Exception:
            logger.warning("_build_entity_block 失败", exc_info=True)
            return ""

    def _build_fact_tag_block(self, seen_facts: set, token_budget: int = None) -> str:
        """冲突6：事实标签块——过织布机加工层，关联来源上下文。

        与显式记忆/高信实体共用 seen_facts 去重；token_budget 用于三块合计预算截断。
        """
        try:
            from weave_l3 import weave_fact_categories_with_context
            lines = weave_fact_categories_with_context(
                limit=5, seen_facts=seen_facts, max_tokens=token_budget
            )
            return "\n".join(lines)
        except Exception:
            logger.warning("_build_fact_tag_block 失败", exc_info=True)
            return ""

    def system_prompt_block(self) -> str:
        """V2.9.8: 四层问答式注入 — 你是谁→往哪走→怎么变成这样→还没做完
        V2.20.3: 内容hash缓存——相同数据必返回与上次字节完全一致的字符串（服务端前缀KV缓存命中）。"""
        injected_rules = []
        try:
            from sandglass_vault import count
            from sandglass_think import comprehensive_offset, _current_stage
            from sandglass_think import _emotional_entropy, search_filter
            from sandglass_paths import _NB

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

            # ═══════ 纪律最前：红牌常驻 + 普通触发（单3） ═══════
            try:
                from discipline import iron_rule_layers, iron_rule_inject_bump
                rule_context_parts = [
                    getattr(self, "_last_rule_context", ""),
                    getattr(self, "_prefetch_last_text", ""),
                    " ".join(getattr(self, "_prefetch_hints", []) or []),
                ]
                rule_context = " ".join([part for part in rule_context_parts if part])
                layers = iron_rule_layers(context=rule_context)
                iron_lines = []
                if layers["red"]:
                    iron_lines.append("铁律：")
                    iron_lines.extend(
                        f"  [red] {item['text']} ×{item['score']}"
                        for item in layers["red"]
                    )
                if layers["normal"]:
                    if not layers["red"]:
                        iron_lines.append("铁律：")
                    iron_lines.extend(
                        f"  [normal] {item['text']} ×{item['score']} [触发:{item['triggered_by']}]"
                        for item in layers["normal"]
                    )
                if iron_lines:
                    blocks.append("\n".join(iron_lines))
                    injected_rules = [
                        item["text"]
                        for item in layers["red"] + layers["normal"]
                    ]
            except Exception:
                logger.debug("铁律双层注入失败", exc_info=True)

            # ═══════ 冲突6：显式记忆/高信实体/事实标签（纪律后、你是谁前） ═══════
            # 三个块共用 seen_facts，失败各自降级，不影响基础注入。
            seen_facts: set = set()
            try:
                explicit_block, explicit_facts = self._build_explicit_memory_block()
                seen_facts.update(explicit_facts)
                if explicit_block:
                    blocks.append(f"【显式记忆】\n{explicit_block}")
            except Exception:
                logger.warning("system_prompt_block 显式记忆块失败", exc_info=True)

            # 三块正文合计 ≤250 token：先按显式块实际成本给高信实体/事实标签分配预算。
            try:
                from discipline import _estimate_tokens
                remaining = max(0, 250 - _estimate_tokens(explicit_block))
                entity_budget = max(0, int(remaining * 0.55))
            except Exception:
                def _estimate_tokens(text: str) -> int:
                    return len(str(text or ""))
                remaining = 250
                entity_budget = 120
            try:
                entity_block = self._build_entity_block(seen_facts, token_budget=entity_budget)
                if entity_block:
                    blocks.append(f"【高信实体】\n{entity_block}")
            except Exception:
                logger.warning("system_prompt_block 高信实体块失败", exc_info=True)
            try:
                entity_cost = _estimate_tokens(entity_block) if "entity_block" in locals() else 0
                fact_budget = max(0, remaining - entity_cost)
                fact_tag_block = self._build_fact_tag_block(seen_facts, token_budget=fact_budget)
                if fact_tag_block:
                    blocks.append(f"【事实标签】\n{fact_tag_block}")
            except Exception:
                logger.warning("system_prompt_block 事实标签块失败", exc_info=True)

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
            except Exception:
                logger.warning("system_prompt_block 身份画像提取失败", exc_info=True)
            
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
            except Exception:
                logger.warning("system_prompt_block five-facets 注入失败", exc_info=True)
            
            # 决策：管道洞察已含偏移方向，此处不重复
            
            # 关注：从fact_tags高频标签
            # V2.20.4: 与 memory_provider.py 同口径——统一走 shadow_sand.shadow_top_tags()
            # （行号门控 + 三道闸 + 内容特征过滤），收编裸连接
            try:
                from collections import Counter
                from shadow_sand import shadow_top_tags
                tags = Counter()
                for t in shadow_top_tags(limit=2000):
                    t = t.strip()
                    if t and len(t) > 1: tags[t] += 1
                top = [t for t,_ in tags.most_common(3) if _ >= 2]
                if top: identity_parts.append(f"关注: {', '.join(top)}")
            except Exception:
                logger.warning("system_prompt_block 高频标签注入失败", exc_info=True)
            
            # 场景
            scene_text = ""
            try:
                from scene_l3 import scene_current
                scenes = scene_current()
                if scenes: scene_text = ", ".join(scenes[:3])
            except Exception:
                logger.warning("system_prompt_block 场景注入失败", exc_info=True)
            
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
                logger.warning("system_prompt_block 画像溯源检查失败", exc_info=True)

            # ═══════ 第二层：你在往哪走（极简） ═══════
            layer2 = []
            # 情绪状态
            if mood != "平稳":
                layer2.append(f"【状态】🎭 {mood}")
            # 最近决策（管道洞察已含，此处只补情绪）
            decisions = []
            try:
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
                logger.warning("system_prompt_block 最近决策读取失败", exc_info=True)
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
                logger.warning("system_prompt_block 情绪偏移提示失败", exc_info=True)

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
                logger.warning("system_prompt_block 待办读取失败", exc_info=True)

            if tasks:
                layer4.append("【还没做完】")
                layer4.append("待办：")
                layer4.extend(f"  {i+1}. {t}" for i, t in enumerate(tasks))
                blocks.append("\n".join(layer4))

            # ═══════ 管道洞察（V2.9.11） ═══════
            try:
                from sandglass_think import _synthesize_3d
                syn = _synthesize_3d(trigger="inject")
                if syn and syn.get("pipe_insights"):
                    blocks.append(f"🔍 {syn['pipe_insights']}")
            except Exception:
                logger.warning("system_prompt_block 管道洞察注入失败", exc_info=True)

            # ═══════ 尾部 ═══════
            blocks.append(f"沙漏: {total}条 | 阶段: {stage}")

            content = "\n\n".join(blocks).strip()
        except Exception:
            logger.warning("system_prompt_block 整体失败", exc_info=True)
            content = "NexSandglass记忆系统已就绪。使用sandglass_search搜索记忆。"
        # V2.20.3: 内容hash缓存——hash相同→复用上次字符串（字节级稳定）；
        # 缓存任何异常→照常返回本次生成内容（异常兜底，不吞注入）
        try:
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            with self._lock:
                if digest == self._inject_cached_hash:
                    return self._inject_cached_text
                self._inject_cached_hash = digest
                self._inject_cached_text = content
        except Exception:
            logger.warning("system_prompt_block hash缓存写入失败", exc_info=True)
        # V2.20.x: 只在真正组装出新 system prompt 后 bump 一次 inject_count；
        # hash 命中会提前 return，因此缓存命中不会自增，读取路径更不会 bump。
        try:
            for r in injected_rules:
                iron_rule_inject_bump(r)
        except Exception:
            logger.warning("铁律注入计数递增失败", exc_info=True)
        return content

    def prefetch(self, query: str, **kwargs) -> str:
        """V2.9.34: 两段式轮次注入 — 搜索上下文+状态快照。~60t。激励LLM主动搜索。
        V2.20.3: 同query 3轮内重复→跳过重算，复用上次快照（字节级稳定）。
        V2.20.5: 签名兼容 Hermes — 接受 session_id 等关键字参数。"""
        try:
            nq = self._normalize_query(query)
            self._last_rule_context = str(query or "")
            if nq:
                with self._lock:
                    if any(self._query_similar(nq, hq) for hq in self._prefetch_query_history):
                        return self._prefetch_last_text  # V2.20.3: 3轮内重复→跳过重算
            parts = []
            
            # ═══ 块A: 搜索上下文 (~25t) ═══
            hints = getattr(self, '_prefetch_hints', [])
            if hints:
                ctx = f"🔍 {' / '.join(hints[:3])}"
                try:
                    from scene_l3 import scene_current
                    sc = scene_current()
                    if sc: ctx += f" | 📍 {sc[0]}"
                except Exception:
                    logger.warning("prefetch 场景注入失败", exc_info=True)
                parts.append(ctx)
            
            # ═══ 块B: 状态快照 (~35t) ═══
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
            lines = [f"状态: {off_d}({off.get('offset',0):+d}%) | {mood}{tangle}"]
            # 铁律：红牌全量 + 普通按触发词；不再硬截 25 字
            try:
                from discipline import iron_rule_layers
                layers = iron_rule_layers(context=(query or ""))
                rule_lines = []
                rule_lines.extend(
                    f"[red] {item['text']} ×{item['score']}"
                    for item in layers["red"]
                )
                rule_lines.extend(
                    f"[normal] {item['text']} ×{item['score']} [触发:{item['triggered_by']}]"
                    for item in layers["normal"]
                )
                if rule_lines:
                    lines.append("铁律：" + " ".join(rule_lines))
            except Exception:
                logger.warning("prefetch 铁律注入失败", exc_info=True)
            # 洞察精简（只取标签+告警）
            if pi:
                snippets = [s.strip() for s in pi.split("|") if s.strip()]
                key = [s[:50] for s in snippets if any(k in s for k in ["标签:", "告警:"])]
                if key: lines.append(" | ".join(key[:2]))
            parts.append("\n".join(lines))
            
            result = "\n".join(parts)
            result = result[:500]  # ~60t 硬截断
            if nq:
                with self._lock:
                    self._prefetch_query_history.append(nq)
                    self._prefetch_last_text = result
            return result
        except Exception:
            return ""

    def queue_prefetch(self, query: str, **kwargs) -> None:
        """后台预热——语义扩展+标签提取。激励LLM主动调sandglass_search。
        V2.20.3: 同query 3轮内重复→跳过，保留上次 hints，避免每轮重复扩展。
        V2.20.5: 签名兼容 Hermes — 接受 session_id 等关键字参数。"""
        try:
            nq = self._normalize_query(query)
            self._last_rule_context = str(query or "")
            if nq:
                with self._lock:
                    if any(self._query_similar(nq, hq) for hq in self._queue_prefetch_query_history):
                        return  # V2.20.3: 3轮内重复→跳过（保留上次 _prefetch_hints）
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
            if nq:
                with self._lock:
                    self._queue_prefetch_query_history.append(nq)
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
            self._last_rule_context = " ".join([
                part for part in (str(user_msg or ""), str(assistant_msg or "")) if part
            ])
            self._turn_count += 1
        except Exception:
            logger.warning("sync_turn 落沙失败", exc_info=True)

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
            logger.warning(f"_handle_fact_store: 局部导入失败: from sandglass_vault import search as vault_search", exc_info=True)
            return tool_error(f"fact_store error: {e}")

    def _handle_fact_feedback(self, args: dict) -> str:
        try:
            from shadow_sand import shadow_feedback
            result = shadow_feedback(args["line_num"], args.get("helpful", True))
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"_handle_fact_feedback: 局部导入失败: from shadow_sand import shadow_feedback", exc_info=True)
            return tool_error(f"fact_feedback error: {e}")

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """会话结束——落沙 + 偏移检查 + V2.9.9.1情绪摘要。V2.20.3: 顺带重置阶段一缓存。"""
        try:
            # V2.20.3: 会话结束→重置阶段一缓存，防串会话（失败不影响落沙）
            try:
                with self._lock:
                    self._reset_stage1_cache()
            except Exception:
                logger.debug("on_session_end 重置阶段一缓存失败（非致命）", exc_info=True)
            # V2.20.x: 会话结束重置铁律注入去重，下一会话可重新统计 inject_count
            try:
                from discipline import iron_rule_session_reset
                iron_rule_session_reset()
            except Exception:
                logger.debug("on_session_end 重置铁律注入去重失败（非致命）", exc_info=True)
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
                logger.warning("on_session_end 情绪摘要失败", exc_info=True)

        except Exception:
            logger.warning("on_session_end 失败", exc_info=True)

    def on_session_switch(self, new_session_id: str, **kwargs) -> None:
        """V2.20.3: 会话切换（/new /reset /resume /branch /压缩）→ 重置阶段一缓存。"""
        try:
            with self._lock:
                if new_session_id:
                    self._session_id = new_session_id
                self._reset_stage1_cache()
        except Exception:
            logger.debug("on_session_switch 重置阶段一缓存失败（非致命）", exc_info=True)

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
            logger.warning("on_memory_write 落沙失败", exc_info=True)

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
            logger.warning("on_pre_compress 提取失败", exc_info=True)
        return None


# ── 插件自动发现入口 ──
def register(ctx) -> None:
    """Hermes 插件加载入口——接收 config 上下文并注册 Provider。"""
    provider = NexSandglassProvider()
    ctx.register_memory_provider(provider)
